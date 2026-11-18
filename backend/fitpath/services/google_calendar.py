"""Autorización persistente y creación idempotente de eventos Calendar."""

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from joserfc import jwe
from joserfc.jwk import OctKey


GOOGLE_CALENDAR_SCOPE = (
    "https://www.googleapis.com/auth/calendar.events.owned"
)
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API_URL = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarError(RuntimeError):
    """Error controlado de la integración Google Calendar."""


class GoogleCalendarConfigurationError(GoogleCalendarError):
    """La integración no tiene una configuración segura completa."""


class GoogleCalendarAuthorizationRequiredError(GoogleCalendarError):
    """El Cliente debe autorizar o volver a autorizar Calendar."""


class GoogleCalendarEnrollmentNotFoundError(GoogleCalendarError):
    """La inscripción no existe, no está activa o no pertenece al Cliente."""


class GoogleCalendarProviderError(GoogleCalendarError):
    """Google no respondió con un resultado utilizable."""


class GoogleCalendarPermissionError(GoogleCalendarProviderError):
    """Google rechazó el token o el alcance autorizado."""


class GoogleCalendarDataError(GoogleCalendarError):
    """Los datos persistidos no permiten construir un evento seguro."""


def _positive_number(value, label, maximum):
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise GoogleCalendarConfigurationError(f"{label} no es válido.") from error
    if parsed <= 0 or parsed > maximum:
        raise GoogleCalendarConfigurationError(f"{label} está fuera de rango.")
    return parsed


def _now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def granted_scopes(value):
    """Normaliza el campo scope sin confiar en su orden ni formato."""
    if isinstance(value, str):
        return frozenset(value.split())
    if isinstance(value, (list, tuple, set, frozenset)):
        return frozenset(str(item) for item in value)
    return frozenset()


@dataclass(frozen=True)
class GoogleCalendarSettings:
    client_id: str
    client_secret: str
    token_secret: str
    timeout_seconds: float

    @classmethod
    def from_mapping(cls, config):
        client_id = str(config.get("GOOGLE_CLIENT_ID") or "").strip()
        client_secret = str(config.get("GOOGLE_CLIENT_SECRET") or "").strip()
        token_secret = str(
            config.get("GOOGLE_CALENDAR_TOKEN_SECRET") or ""
        ).strip()
        if not client_id or not client_secret:
            raise GoogleCalendarConfigurationError(
                "Faltan las credenciales OAuth web de Google."
            )
        if len(token_secret) < 32:
            raise GoogleCalendarConfigurationError(
                "GOOGLE_CALENDAR_TOKEN_SECRET debe tener al menos 32 caracteres."
            )
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            token_secret=token_secret,
            timeout_seconds=_positive_number(
                config.get("GOOGLE_CALENDAR_TIMEOUT_SECONDS"),
                "GOOGLE_CALENDAR_TIMEOUT_SECONDS",
                30,
            ),
        )

    @property
    def encryption_key(self):
        return hashlib.sha256(self.token_secret.encode("utf-8")).digest()


def _encrypt_refresh_token(refresh_token, settings):
    token = str(refresh_token or "").strip()
    if not token:
        raise GoogleCalendarAuthorizationRequiredError(
            "Google no entregó un refresh token."
        )
    encrypted = jwe.encrypt_compact(
        {"alg": "dir", "enc": "A256GCM"},
        token.encode("utf-8"),
        OctKey.import_key(settings.encryption_key),
    )
    return encrypted.decode("ascii") if isinstance(encrypted, bytes) else encrypted


def _decrypt_refresh_token(encrypted, settings):
    try:
        payload = jwe.decrypt_compact(
            encrypted, OctKey.import_key(settings.encryption_key)
        ).plaintext
        token = payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)
    except Exception as error:
        raise GoogleCalendarAuthorizationRequiredError(
            "La autorización de Calendar ya no se puede utilizar."
        ) from error
    if not token.strip():
        raise GoogleCalendarAuthorizationRequiredError(
            "La autorización de Calendar no contiene un token válido."
        )
    return token


def save_calendar_authorization(
    connection, user_id, refresh_token, scope_value, settings
):
    """Cifra y guarda el refresh token, aislado por usuario FitPath."""
    scopes = granted_scopes(scope_value)
    if GOOGLE_CALENDAR_SCOPE not in scopes or "openid" not in scopes:
        raise GoogleCalendarAuthorizationRequiredError(
            "No se concedieron todos los alcances requeridos."
        )
    encrypted = _encrypt_refresh_token(refresh_token, settings)
    now = _now_utc()
    connection.execute(
        """
        INSERT INTO autorizaciones_google_calendar
            (usuario_id, refresh_token_cifrado, alcance, creado_utc, actualizado_utc)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(usuario_id) DO UPDATE SET
            refresh_token_cifrado = excluded.refresh_token_cifrado,
            alcance = excluded.alcance,
            actualizado_utc = excluded.actualizado_utc
        """,
        (user_id, encrypted, " ".join(sorted(scopes)), now, now),
    )
    connection.commit()


def calendar_connection_status(connection, user_id, settings):
    row = connection.execute(
        """
        SELECT refresh_token_cifrado, alcance
        FROM autorizaciones_google_calendar
        WHERE usuario_id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return {"configured": True, "connected": False, "state": "authorization_required"}
    try:
        _decrypt_refresh_token(row["refresh_token_cifrado"], settings)
    except GoogleCalendarAuthorizationRequiredError:
        return {"configured": True, "connected": False, "state": "authorization_error"}
    if GOOGLE_CALENDAR_SCOPE not in granted_scopes(row["alcance"]):
        return {"configured": True, "connected": False, "state": "authorization_error"}
    return {"configured": True, "connected": True, "state": "connected"}


class GoogleCalendarClient:
    """Cliente REST mínimo; no incorpora el SDK completo de Google."""

    def __init__(self, settings, session=None):
        self.settings = settings
        self.session = session or requests.Session()

    @staticmethod
    def _payload(response):
        try:
            payload = response.json()
        except (ValueError, TypeError) as error:
            raise GoogleCalendarProviderError(
                "Google Calendar no devolvió JSON válido."
            ) from error
        if not isinstance(payload, dict):
            raise GoogleCalendarProviderError(
                "Google Calendar devolvió una respuesta inválida."
            )
        return payload

    def refresh_access_token(self, refresh_token):
        try:
            response = self.session.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.settings.client_id,
                    "client_secret": self.settings.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                headers={"Accept": "application/json"},
                timeout=self.settings.timeout_seconds,
            )
        except requests.RequestException as error:
            raise GoogleCalendarProviderError(
                "No se pudo renovar el acceso a Google Calendar."
            ) from error
        payload = self._payload(response)
        if response.status_code in {400, 401}:
            raise GoogleCalendarPermissionError(
                "Google rechazó la autorización de Calendar."
            )
        if not 200 <= response.status_code < 300:
            raise GoogleCalendarProviderError(
                "Google no pudo renovar el acceso a Calendar."
            )
        access_token = str(payload.get("access_token") or "").strip()
        scopes = granted_scopes(payload.get("scope"))
        if not access_token or (
            scopes and GOOGLE_CALENDAR_SCOPE not in scopes
        ):
            raise GoogleCalendarPermissionError(
                "El token renovado no autoriza eventos de Calendar."
            )
        return access_token

    def _calendar_request(self, method, path, access_token, *, json=None):
        try:
            return self.session.request(
                method,
                f"{GOOGLE_CALENDAR_API_URL}{path}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=json,
                timeout=self.settings.timeout_seconds,
            )
        except requests.RequestException as error:
            raise GoogleCalendarProviderError(
                "No se pudo contactar Google Calendar."
            ) from error

    def _existing_event(self, access_token, event_id):
        response = self._calendar_request(
            "GET",
            f"/calendars/primary/events/{quote(event_id, safe='')}",
            access_token,
        )
        if response.status_code in {401, 403}:
            raise GoogleCalendarPermissionError(
                "Google rechazó el acceso al evento."
            )
        if not 200 <= response.status_code < 300:
            raise GoogleCalendarProviderError(
                "Google no permitió recuperar el evento existente."
            )
        return self._payload(response)

    def insert_event(self, access_token, event):
        response = self._calendar_request(
            "POST", "/calendars/primary/events", access_token, json=event
        )
        if response.status_code == 409:
            return self._existing_event(access_token, event["id"]), True
        if response.status_code in {401, 403}:
            raise GoogleCalendarPermissionError(
                "Google rechazó la creación del evento."
            )
        if not 200 <= response.status_code < 300:
            raise GoogleCalendarProviderError(
                "Google no pudo crear el evento."
            )
        return self._payload(response), False


def _event_identifier(user_id, enrollment_id):
    digest = hashlib.sha256(
        f"fitpath:{user_id}:{enrollment_id}".encode("ascii")
    ).hexdigest()
    return f"fitpath{digest}"


def _local_datetime(value, time_zone):
    try:
        instant = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        zone = ZoneInfo(time_zone)
    except (TypeError, ValueError, ZoneInfoNotFoundError) as error:
        raise GoogleCalendarDataError(
            "La fecha o zona horaria de la clase no es válida."
        ) from error
    return instant.astimezone(zone).isoformat()


def _event_body(row, user_id):
    event_id = _event_identifier(user_id, row["id_inscripcion"])
    return {
        "id": event_id,
        "summary": f"FitPath · {row['actividad']}",
        "description": (
            f"Clase de {row['actividad']} en {row['sede']}. "
            f"Inscripción FitPath #{row['id_inscripcion']}."
        ),
        "location": f"{row['sede']} · {row['direccion']}",
        "start": {
            "dateTime": _local_datetime(row["inicio_utc"], row["zona_horaria"]),
            "timeZone": row["zona_horaria"],
        },
        "end": {
            "dateTime": _local_datetime(row["fin_utc"], row["zona_horaria"]),
            "timeZone": row["zona_horaria"],
        },
        "visibility": "private",
        "extendedProperties": {
            "private": {
                "fitpathEnrollmentId": str(row["id_inscripcion"]),
                "fitpathUserId": str(user_id),
            }
        },
    }


def _event_result(row, *, created):
    return {
        "enrollment_id": row["inscripcion_id"],
        "event_url": row["google_event_url"],
        "created": created,
    }


def create_enrollment_calendar_event(
    connection,
    user_id,
    client_id,
    enrollment_id,
    settings,
    provider=None,
):
    """Crea una vez el evento de una inscripción activa y propia."""
    existing = connection.execute(
        """
        SELECT inscripcion_id, google_event_url
        FROM eventos_google_calendar
        WHERE usuario_id = ? AND inscripcion_id = ?
        """,
        (user_id, enrollment_id),
    ).fetchone()
    if existing is not None:
        return _event_result(existing, created=False)

    row = connection.execute(
        """
        SELECT i.id_inscripcion, a.nombre AS actividad,
               s.nombre AS sede, s.direccion, s.zona_horaria,
               c.inicio_utc, c.fin_utc
        FROM inscripciones AS i
        JOIN clases AS c ON c.id_clase = i.clase_id
        JOIN actividades AS a ON a.id_actividad = c.actividad_id
        JOIN sedes AS s ON s.id_sede = c.sede_id
        WHERE i.id_inscripcion = ? AND i.cliente_id = ?
          AND i.estado = 'activa' AND c.estado = 'programada'
        """,
        (enrollment_id, client_id),
    ).fetchone()
    if row is None:
        raise GoogleCalendarEnrollmentNotFoundError(
            "La inscripción no está disponible para Calendar."
        )

    authorization = connection.execute(
        """
        SELECT refresh_token_cifrado
        FROM autorizaciones_google_calendar
        WHERE usuario_id = ?
        """,
        (user_id,),
    ).fetchone()
    if authorization is None:
        raise GoogleCalendarAuthorizationRequiredError(
            "Google Calendar todavía no está autorizado."
        )
    refresh_token = _decrypt_refresh_token(
        authorization["refresh_token_cifrado"], settings
    )
    calendar = provider or GoogleCalendarClient(settings)
    access_token = calendar.refresh_access_token(refresh_token)
    event_request = _event_body(row, user_id)
    event, recovered = calendar.insert_event(access_token, event_request)

    event_id = str(event.get("id") or "").strip()
    private = (event.get("extendedProperties") or {}).get("private") or {}
    if (
        event_id != event_request["id"]
        or str(private.get("fitpathEnrollmentId")) != str(enrollment_id)
        or str(private.get("fitpathUserId")) != str(user_id)
    ):
        raise GoogleCalendarProviderError(
            "Google devolvió un evento que no corresponde a la inscripción."
        )
    event_url = str(event.get("htmlLink") or "").strip() or None
    if event_url and urlsplit(event_url).scheme != "https":
        raise GoogleCalendarProviderError(
            "Google devolvió un enlace de evento no seguro."
        )

    try:
        connection.execute(
            """
            INSERT INTO eventos_google_calendar
                (usuario_id, inscripcion_id, google_calendar_id,
                 google_event_id, google_event_url, creado_utc)
            VALUES (?, ?, 'primary', ?, ?, ?)
            """,
            (user_id, enrollment_id, event_id, event_url, _now_utc()),
        )
        connection.commit()
        created = not recovered
    except sqlite3.IntegrityError:
        connection.rollback()
        created = False

    stored = connection.execute(
        """
        SELECT inscripcion_id, google_event_url
        FROM eventos_google_calendar
        WHERE usuario_id = ? AND inscripcion_id = ?
        """,
        (user_id, enrollment_id),
    ).fetchone()
    if stored is None:
        raise GoogleCalendarError(
            "No se pudo registrar el identificador del evento."
        )
    return _event_result(stored, created=created)
