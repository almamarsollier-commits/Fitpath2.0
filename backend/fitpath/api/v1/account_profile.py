"""Consulta y edición segura del perfil propio de cualquier usuario activo."""

import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from ...auth.authorization import current_identity, require_api_access
from ...database import get_db


account_profile_api_blueprint = Blueprint(
    "account_profile_api", __name__, url_prefix="/api/v1/me/profile"
)
authenticated_profile_required = require_api_access()

EDITABLE_FIELDS = frozenset(
    {
        "nombre",
        "apellido",
        "nombre_usuario",
        "telefono",
        "biografia",
        "preferencias",
        "objetivos",
    }
)
FORBIDDEN_FIELDS = frozenset(
    {
        "id",
        "id_usuario",
        "usuario_id",
        "email",
        "rol",
        "role",
        "rol_id",
        "activo",
        "estado",
        "subject",
        "google_subject",
        "permisos",
    }
)
USERNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9])?$")
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 ()-]{5,23}[0-9]$")
DEFAULT_PREFERENCES = {
    "tema": "sistema",
    "movimiento_reducido": False,
    "recordatorios_clase": True,
}
PREFERENCE_KEYS = frozenset(DEFAULT_PREFERENCES)


class ProfileValidationError(ValueError):
    """El cuerpo no cumple el contrato público del perfil."""

    def __init__(self, message, *, field=None, error="invalid_profile"):
        super().__init__(message)
        self.field = field
        self.error = error


@account_profile_api_blueprint.after_request
def disable_private_cache(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _csrf_is_valid():
    identity = current_identity()
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = identity["csrf_token"] if identity else ""
    import hmac

    return bool(supplied and expected and hmac.compare_digest(supplied, expected))


def _clean_text(value, field, *, minimum=1, maximum=80, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ProfileValidationError("El valor debe ser texto.", field=field)
    normalized = unicodedata.normalize("NFC", value).strip()
    if optional and not normalized:
        return None
    if not minimum <= len(normalized) <= maximum:
        raise ProfileValidationError(
            f"Debe tener entre {minimum} y {maximum} caracteres.", field=field
        )
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise ProfileValidationError("Contiene caracteres no permitidos.", field=field)
    return normalized


def _person_name(value, field):
    normalized = _clean_text(value, field, maximum=80)
    if not any(character.isalpha() for character in normalized):
        raise ProfileValidationError("Debe incluir al menos una letra.", field=field)
    if any(
        not (character.isalpha() or character in " '-")
        for character in normalized
    ):
        raise ProfileValidationError(
            "Solo se permiten letras, espacios, apóstrofes y guiones.", field=field
        )
    return " ".join(normalized.split())


def _username(value):
    normalized = _clean_text(value, "nombre_usuario", minimum=3, maximum=30).lower()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ProfileValidationError(
            "Usá de 3 a 30 letras minúsculas, números, punto, guion o guion bajo.",
            field="nombre_usuario",
        )
    return normalized


def _phone(value):
    normalized = _clean_text(
        value, "telefono", minimum=8, maximum=25, optional=True
    )
    if normalized is not None and not PHONE_PATTERN.fullmatch(normalized):
        raise ProfileValidationError(
            "Ingresá un teléfono válido con código de área.", field="telefono"
        )
    return normalized


def _preferences(value, current):
    if not isinstance(value, dict):
        raise ProfileValidationError(
            "Las preferencias deben ser un objeto.", field="preferencias"
        )
    unknown = set(value) - PREFERENCE_KEYS
    if unknown:
        raise ProfileValidationError(
            "Hay preferencias no admitidas.", field="preferencias"
        )
    result = {**DEFAULT_PREFERENCES, **current}
    if "tema" in value:
        if value["tema"] not in {"claro", "oscuro", "sistema"}:
            raise ProfileValidationError(
                "El tema debe ser claro, oscuro o sistema.", field="preferencias.tema"
            )
        result["tema"] = value["tema"]
    for key in ("movimiento_reducido", "recordatorios_clase"):
        if key in value:
            if not isinstance(value[key], bool):
                raise ProfileValidationError(
                    "La preferencia debe ser verdadera o falsa.",
                    field=f"preferencias.{key}",
                )
            result[key] = value[key]
    return result


def _objective_ids(value):
    if not isinstance(value, list) or len(value) > 10:
        raise ProfileValidationError(
            "Los objetivos deben ser una lista de hasta 10 IDs.", field="objetivos"
        )
    if any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in value):
        raise ProfileValidationError(
            "Cada objetivo debe usar un ID válido.", field="objetivos"
        )
    if len(set(value)) != len(value):
        raise ProfileValidationError(
            "No repitas objetivos.", field="objetivos"
        )
    return value


def _stored_preferences(value):
    try:
        stored = json.loads(value or "{}")
    except (TypeError, ValueError):
        stored = {}
    return stored if isinstance(stored, dict) else {}


def _profile_payload(user_id):
    connection = get_db()
    user = connection.execute(
        """
        SELECT
            u.id_usuario, u.nombre, u.apellido, u.nombre_usuario,
            u.email, u.telefono, u.activo, r.nombre AS rol,
            p.biografia, p.preferencias_json, p.actualizado_utc
        FROM usuarios AS u
        JOIN roles AS r ON r.id_rol = u.rol_id
        LEFT JOIN perfiles_usuario AS p ON p.usuario_id = u.id_usuario
        WHERE u.id_usuario = ? AND u.activo = 1
        """,
        (user_id,),
    ).fetchone()
    if user is None:
        return None
    preferences = {**DEFAULT_PREFERENCES, **_stored_preferences(user["preferencias_json"])}
    objectives = []
    objective_catalog = []
    if user["rol"] == "Cliente":
        client = connection.execute(
            "SELECT id_cliente FROM clientes WHERE usuario_id = ?", (user_id,)
        ).fetchone()
        if client is not None:
            objectives = [
                row[0]
                for row in connection.execute(
                    "SELECT objetivo_id FROM cliente_objetivo WHERE cliente_id = ? ORDER BY objetivo_id",
                    (client["id_cliente"],),
                ).fetchall()
            ]
            objective_catalog = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT o.id_objetivo AS id, o.nombre, o.descripcion,
                           t.nombre AS tipo
                    FROM objetivos AS o
                    JOIN tipos_objetivo AS t
                      ON t.id_tipo_objetivo = o.tipo_objetivo_id
                    ORDER BY t.nombre, o.nombre, o.id_objetivo
                    """
                ).fetchall()
            ]
    return {
        "id": user["id_usuario"],
        "nombre": user["nombre"],
        "apellido": user["apellido"],
        "nombre_usuario": user["nombre_usuario"],
        "email": user["email"],
        "telefono": user["telefono"],
        "rol": user["rol"],
        "biografia": user["biografia"],
        "preferencias": preferences,
        "objetivos": objectives,
        "catalogo_objetivos": objective_catalog,
        "actualizado_utc": user["actualizado_utc"],
    }


def _validated_updates(payload, profile):
    if not isinstance(payload, dict) or not payload:
        raise ProfileValidationError("Enviá al menos un campo editable.")
    supplied = set(payload)
    rejected = supplied & FORBIDDEN_FIELDS
    unknown = supplied - EDITABLE_FIELDS - FORBIDDEN_FIELDS
    if rejected or unknown:
        fields = sorted(rejected | unknown)
        raise ProfileValidationError(
            "Hay campos que no se pueden modificar.",
            field=",".join(fields),
            error="fields_not_allowed",
        )

    updates = {}
    if "nombre" in payload:
        updates["nombre"] = _person_name(payload["nombre"], "nombre")
    if "apellido" in payload:
        updates["apellido"] = _person_name(payload["apellido"], "apellido")
    if "nombre_usuario" in payload:
        updates["nombre_usuario"] = _username(payload["nombre_usuario"])
    if "telefono" in payload:
        updates["telefono"] = _phone(payload["telefono"])
    if "biografia" in payload:
        updates["biografia"] = _clean_text(
            payload["biografia"], "biografia", maximum=500, optional=True
        )
    if "preferencias" in payload:
        updates["preferencias"] = _preferences(
            payload["preferencias"], profile["preferencias"]
        )
    if "objetivos" in payload:
        if profile["rol"] != "Cliente":
            raise ProfileValidationError(
                "Los objetivos de entrenamiento solo corresponden al perfil Cliente.",
                field="objetivos",
                error="field_not_applicable",
            )
        updates["objetivos"] = _objective_ids(payload["objetivos"])
    return updates


def _save_updates(user_id, updates):
    connection = get_db()
    try:
        connection.execute("BEGIN IMMEDIATE")
        user_values = {
            key: value
            for key, value in updates.items()
            if key in {"nombre", "apellido", "nombre_usuario", "telefono"}
        }
        if user_values:
            assignments = ", ".join(f"{key} = ?" for key in user_values)
            connection.execute(
                f"UPDATE usuarios SET {assignments} WHERE id_usuario = ?",
                (*user_values.values(), user_id),
            )

        if "biografia" in updates or "preferencias" in updates:
            current = connection.execute(
                "SELECT biografia, preferencias_json FROM perfiles_usuario WHERE usuario_id = ?",
                (user_id,),
            ).fetchone()
            biography = updates.get(
                "biografia", current["biografia"] if current is not None else None
            )
            preferences = updates.get(
                "preferencias",
                _stored_preferences(
                    current["preferencias_json"] if current is not None else "{}"
                ),
            )
            connection.execute(
                """
                INSERT INTO perfiles_usuario
                    (usuario_id, biografia, preferencias_json, actualizado_utc)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(usuario_id) DO UPDATE SET
                    biografia = excluded.biografia,
                    preferencias_json = excluded.preferencias_json,
                    actualizado_utc = excluded.actualizado_utc
                """,
                (
                    user_id,
                    biography,
                    json.dumps(preferences, ensure_ascii=False, separators=(",", ":")),
                    _utc_now(),
                ),
            )

        if "objetivos" in updates:
            client = connection.execute(
                "SELECT id_cliente FROM clientes WHERE usuario_id = ?", (user_id,)
            ).fetchone()
            if client is None:
                raise ProfileValidationError(
                    "El usuario no tiene un perfil Cliente.",
                    field="objetivos",
                    error="client_profile_required",
                )
            objective_ids = updates["objetivos"]
            if objective_ids:
                placeholders = ",".join("?" for _ in objective_ids)
                count = connection.execute(
                    f"SELECT count(*) FROM objetivos WHERE id_objetivo IN ({placeholders})",
                    objective_ids,
                ).fetchone()[0]
                if count != len(objective_ids):
                    raise ProfileValidationError(
                        "Uno o más objetivos no existen.", field="objetivos"
                    )
            connection.execute(
                "DELETE FROM cliente_objetivo WHERE cliente_id = ?",
                (client["id_cliente"],),
            )
            connection.executemany(
                "INSERT INTO cliente_objetivo (cliente_id, objetivo_id) VALUES (?, ?)",
                ((client["id_cliente"], objective_id) for objective_id in objective_ids),
            )
        connection.commit()
    except ProfileValidationError:
        connection.rollback()
        raise
    except sqlite3.IntegrityError as error:
        connection.rollback()
        if "usuarios.nombre_usuario" in str(error):
            raise ProfileValidationError(
                "Ese nombre de usuario ya está en uso.",
                field="nombre_usuario",
                error="username_unavailable",
            ) from error
        raise ProfileValidationError("No se pudo validar el perfil.") from error
    except sqlite3.Error:
        connection.rollback()
        raise


@account_profile_api_blueprint.get("")
@authenticated_profile_required
def get_own_profile():
    identity = current_identity()
    profile = _profile_payload(identity["user"]["id"])
    if profile is None:
        return jsonify({"error": "profile_not_found"}), 404
    return jsonify({"profile": profile})


@account_profile_api_blueprint.patch("")
@authenticated_profile_required
def update_own_profile():
    if not _csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    identity = current_identity()
    profile = _profile_payload(identity["user"]["id"])
    if profile is None:
        return jsonify({"error": "profile_not_found"}), 404
    try:
        updates = _validated_updates(request.get_json(silent=True), profile)
        _save_updates(identity["user"]["id"], updates)
    except ProfileValidationError as error:
        payload = {"error": error.error, "message": str(error)}
        if error.field:
            payload["field"] = error.field
        status = 409 if error.error == "username_unavailable" else 400
        return jsonify(payload), status
    except sqlite3.Error:
        g.pop("fitpath_identity", None)
        return jsonify({"error": "profile_update_failed"}), 500
    g.pop("fitpath_identity", None)
    return jsonify({"profile": _profile_payload(identity["user"]["id"])})
