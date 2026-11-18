import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.fitpath import create_app
from backend.fitpath.auth import GOOGLE_ISSUER
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.seeds import seed_initial_permissions, seed_initial_roles
from backend.fitpath.services.google_calendar import (
    GOOGLE_CALENDAR_SCOPE,
    GoogleCalendarEnrollmentNotFoundError,
    GoogleCalendarSettings,
    calendar_connection_status,
    create_enrollment_calendar_event,
    save_calendar_authorization,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPOSITORY_ROOT / "backend" / "fitpath" / "migrations"
CLIENT_DATA_SCRIPT = REPOSITORY_ROOT / "statics" / "js" / "modules" / "client-data.js"
RESERVATIONS_VIEW = REPOSITORY_ROOT / "templates" / "cliente" / "clases" / "reservas.html"


class FakeCalendarProvider:
    def __init__(self):
        self.refresh_tokens = []
        self.events = []

    def refresh_access_token(self, refresh_token):
        self.refresh_tokens.append(refresh_token)
        return "short-lived-access-token"

    def insert_event(self, access_token, event):
        self.events.append((access_token, event))
        response = {
            "id": event["id"],
            "htmlLink": "https://calendar.google.com/calendar/event?eid=opaque",
            "extendedProperties": event["extendedProperties"],
        }
        return response, False


class GoogleCalendarTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database_path = Path(temporary.name) / "calendar.sqlite3"
        self.app = create_app(
            "testing",
            {
                "DATABASE": str(self.database_path),
                "MIGRATIONS_DIR": str(MIGRATIONS_DIR),
                "SECRET_KEY": "calendar-session-secret-for-tests",
                "GOOGLE_CLIENT_ID": "calendar-client-id",
                "GOOGLE_CLIENT_SECRET": "calendar-client-secret",
                "GOOGLE_CALENDAR_REDIRECT_URI": (
                    "http://localhost/auth/google/calendar/callback"
                ),
                "GOOGLE_CALENDAR_TOKEN_SECRET": (
                    "calendar-token-secret-with-more-than-thirty-two-characters"
                ),
                "GOOGLE_CALENDAR_TIMEOUT_SECONDS": "5",
                "SESSION_COOKIE_SECURE": False,
            },
        )
        self.client = self.app.test_client()
        self.db = connect_database(self.database_path)
        self.addCleanup(self.db.close)
        self.assertEqual(
            apply_migrations(self.db, MIGRATIONS_DIR), tuple(range(1, 15))
        )
        seed_initial_roles(self.db)
        seed_initial_permissions(self.db)
        self.client_user_id = self._user("Cliente", "calendar-client")
        self.other_user_id = self._user("Cliente", "calendar-other")
        self.admin_user_id = self._user("Administrador", "calendar-admin")
        self.trainer_user_id = self._user("Entrenador", "calendar-trainer")
        self.client_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)",
            (self.client_user_id,),
        ).lastrowid
        self.other_client_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)",
            (self.other_user_id,),
        ).lastrowid
        self.db.execute(
            """
            INSERT INTO identidades_google
                (usuario_id, emisor, subject, creado_utc)
            VALUES (?, ?, 'calendar-google-subject', '2026-11-18T12:00:00Z')
            """,
            (self.client_user_id, GOOGLE_ISSUER),
        )
        site_id = self.db.execute(
            """
            INSERT INTO sedes (nombre, direccion, zona_horaria)
            VALUES ('Palermo', 'Av. Santa Fe 4000',
                    'America/Argentina/Buenos_Aires')
            """
        ).lastrowid
        trainer_id = self.db.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, 'Yoga')",
            (self.trainer_user_id,),
        ).lastrowid
        self.db.execute(
            """
            INSERT INTO entrenador_sede (entrenador_id, sede_id, activo)
            VALUES (?, ?, 1)
            """,
            (trainer_id, site_id),
        )
        activity_id = self.db.execute(
            "INSERT INTO actividades (nombre) VALUES ('Yoga Flow')"
        ).lastrowid
        self.db.execute(
            """
            INSERT INTO actividad_sede (actividad_id, sede_id, habilitada)
            VALUES (?, ?, 1)
            """,
            (activity_id, site_id),
        )
        class_id = self.db.execute(
            """
            INSERT INTO clases
                (actividad_id, sede_id, entrenador_id, inicio_utc, fin_utc,
                 cupo_maximo, estado)
            VALUES (?, ?, ?, '2035-01-10T18:00:00Z',
                    '2035-01-10T19:00:00Z', 10, 'programada')
            """,
            (activity_id, site_id, trainer_id),
        ).lastrowid
        self.enrollment_id = self.db.execute(
            """
            INSERT INTO inscripciones
                (cliente_id, clase_id, fecha_utc, estado)
            VALUES (?, ?, '2026-11-18T12:00:00Z', 'activa')
            """,
            (self.client_id, class_id),
        ).lastrowid
        self.db.commit()
        self.settings = GoogleCalendarSettings.from_mapping(self.app.config)

    def _role(self, name):
        return self.db.execute(
            "SELECT id_rol FROM roles WHERE nombre = ?", (name,)
        ).fetchone()[0]

    def _user(self, role, username):
        return self.db.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES (?, 'Calendar', ?, ?, ?, 1)
            """,
            (
                role,
                username,
                f"{username}@example.test",
                self._role(role),
            ),
        ).lastrowid

    def _login(self, user_id=None):
        with self.client.session_transaction() as session:
            session["fitpath_user_id"] = user_id or self.client_user_id
            session["csrf_token"] = "calendar-csrf"

    def _authorize(self, refresh_token="private-refresh-token"):
        save_calendar_authorization(
            self.db,
            self.client_user_id,
            refresh_token,
            f"openid {GOOGLE_CALENDAR_SCOPE}",
            self.settings,
        )

    def test_login_scope_is_unchanged_and_calendar_uses_incremental_authorization(self):
        with self.app.app_context():
            oauth = self.app.extensions["authlib.integrations.flask_client"]
            self.assertEqual(
                oauth.create_client("google").client_kwargs["scope"],
                "openid email profile",
            )
            self.assertEqual(
                oauth.create_client("google_calendar").client_kwargs["scope"],
                f"openid {GOOGLE_CALENDAR_SCOPE}",
            )

        self._login()
        provider = Mock()
        provider.authorize_redirect.return_value = (
            "redirect",
            302,
            {"Location": "https://accounts.google.com/o/oauth2/v2/auth?state=opaque"},
        )
        with patch("backend.fitpath.auth.calendar_routes.get_oauth") as get_oauth:
            get_oauth().create_client.return_value = provider
            response = self.client.get("/auth/google/calendar/connect")
        self.assertEqual(response.status_code, 302)
        get_oauth().create_client.assert_called_once_with("google_calendar")
        kwargs = provider.authorize_redirect.call_args.kwargs
        self.assertEqual(kwargs["access_type"], "offline")
        self.assertEqual(kwargs["include_granted_scopes"], "true")
        self.assertEqual(kwargs["prompt"], "consent")
        self.assertEqual(kwargs["login_hint"], "calendar-google-subject")
        self.assertTrue(kwargs["nonce"])
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM eventos_google_calendar"
            ).fetchone()[0],
            0,
        )

    def test_callback_binds_account_and_encrypts_refresh_token_without_creating_events(self):
        self._login()
        with self.client.session_transaction() as session:
            session["google_calendar_nonce"] = "calendar-nonce"
            session["google_calendar_user_id"] = self.client_user_id
        provider = Mock()
        provider.authorize_access_token.return_value = {
            "refresh_token": "refresh-token-must-not-be-stored-in-plain-text",
            "scope": f"openid {GOOGLE_CALENDAR_SCOPE}",
            "userinfo": {
                "iss": GOOGLE_ISSUER,
                "sub": "calendar-google-subject",
                "nonce": "calendar-nonce",
            },
        }
        with patch("backend.fitpath.auth.calendar_routes.get_oauth") as get_oauth:
            get_oauth().create_client.return_value = provider
            response = self.client.get("/auth/google/calendar/callback")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("?calendar=connected"))
        stored = self.db.execute(
            """
            SELECT refresh_token_cifrado
            FROM autorizaciones_google_calendar
            WHERE usuario_id = ?
            """,
            (self.client_user_id,),
        ).fetchone()[0]
        self.assertNotIn("refresh-token-must-not-be-stored", stored)
        self.assertEqual(stored.count("."), 4)
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM eventos_google_calendar"
            ).fetchone()[0],
            0,
        )

        with self.client.session_transaction() as session:
            session["google_calendar_nonce"] = "other-nonce"
            session["google_calendar_user_id"] = self.client_user_id
        provider.authorize_access_token.return_value["userinfo"].update(
            {"sub": "another-google-account", "nonce": "other-nonce"}
        )
        with patch("backend.fitpath.auth.calendar_routes.get_oauth") as get_oauth:
            get_oauth().create_client.return_value = provider
            mismatch = self.client.get("/auth/google/calendar/callback")
        self.assertTrue(mismatch.location.endswith("?calendar=account_mismatch"))

    def test_event_uses_real_class_data_timezone_and_is_idempotent_and_owned(self):
        self._authorize()
        provider = FakeCalendarProvider()
        created = create_enrollment_calendar_event(
            self.db,
            self.client_user_id,
            self.client_id,
            self.enrollment_id,
            self.settings,
            provider,
        )
        self.assertTrue(created["created"])
        self.assertEqual(provider.refresh_tokens, ["private-refresh-token"])
        event = provider.events[0][1]
        self.assertEqual(event["summary"], "FitPath · Yoga Flow")
        self.assertEqual(event["location"], "Palermo · Av. Santa Fe 4000")
        self.assertEqual(event["start"]["dateTime"], "2035-01-10T15:00:00-03:00")
        self.assertEqual(event["end"]["dateTime"], "2035-01-10T16:00:00-03:00")
        self.assertEqual(
            event["start"]["timeZone"], "America/Argentina/Buenos_Aires"
        )
        self.assertEqual(event["visibility"], "private")

        repeated = create_enrollment_calendar_event(
            self.db,
            self.client_user_id,
            self.client_id,
            self.enrollment_id,
            self.settings,
            provider,
        )
        self.assertFalse(repeated["created"])
        self.assertEqual(len(provider.events), 1)
        with self.assertRaises(GoogleCalendarEnrollmentNotFoundError):
            create_enrollment_calendar_event(
                self.db,
                self.other_user_id,
                self.other_client_id,
                self.enrollment_id,
                self.settings,
                provider,
            )

    def test_api_requires_session_role_permission_csrf_and_explicit_post(self):
        path = f"/api/v1/client/calendar/enrollments/{self.enrollment_id}/event"
        self.assertEqual(self.client.post(path).status_code, 401)
        self._login(self.admin_user_id)
        self.assertEqual(self.client.post(path).status_code, 403)
        self._login()
        self.assertEqual(self.client.post(path).status_code, 400)
        self._authorize()
        provider = FakeCalendarProvider()
        with patch(
            "backend.fitpath.services.google_calendar.GoogleCalendarClient",
            return_value=provider,
        ):
            response = self.client.post(
                path, headers={"X-CSRF-Token": "calendar-csrf"}
            )
            repeated = self.client.post(
                path, headers={"X-CSRF-Token": "calendar-csrf"}
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(len(provider.events), 1)
        enrollments = self.client.get("/api/v1/client/enrollments")
        self.assertEqual(enrollments.status_code, 200)
        self.assertEqual(enrollments.json["enrollments"][0]["calendar_event_added"], 1)

    def test_status_and_interface_expose_configuration_authorization_success_and_error(self):
        self._login()
        status = self.client.get("/api/v1/client/calendar/status")
        self.assertEqual(
            status.json,
            {
                "configured": True,
                "connected": False,
                "state": "authorization_required",
            },
        )
        self._authorize()
        self.assertEqual(
            calendar_connection_status(
                self.db, self.client_user_id, self.settings
            )["state"],
            "connected",
        )
        self.app.config["GOOGLE_CALENDAR_TOKEN_SECRET"] = None
        unconfigured = self.client.get("/api/v1/client/calendar/status")
        self.assertFalse(unconfigured.json["configured"])

        script = CLIENT_DATA_SCRIPT.read_text(encoding="utf-8")
        view = RESERVATIONS_VIEW.read_text(encoding="utf-8")
        self.assertIn("window.confirm", script)
        self.assertIn("calendar_authorization_expired", script)
        self.assertIn("data-calendar-enrollment", script)
        self.assertIn("data-client-calendar-root", view)
        self.assertIn("FitPath sólo añadirá una clase cuando lo confirmes", view)


if __name__ == "__main__":
    unittest.main()
