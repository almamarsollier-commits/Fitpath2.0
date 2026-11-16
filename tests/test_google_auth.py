"""Pruebas de OIDC Google aisladas del proveedor externo."""

import hashlib
import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import Mock, patch

from authlib.integrations.base_client.errors import MismatchingStateError, OAuthError
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption
from joserfc import jwt
from joserfc.jwk import RSAKey

from backend.fitpath import create_app
from backend.fitpath.auth import GOOGLE_ISSUER
from backend.fitpath.auth.client_views import CLIENT_VIEW_PATHS
from backend.fitpath.auth.demo import create_demo_client, create_local_client
from backend.fitpath.auth.provision import approve_link
from backend.fitpath.config import BaseConfig
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.seeds import seed_initial_permissions


class GoogleAuthTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "fitpath.sqlite3"
        self.app = create_app(
            "testing",
            {
                "DATABASE": str(self.database_path),
                "SECRET_KEY": "test-secret-key-that-is-not-used-outside-tests",
                "GOOGLE_CLIENT_ID": "client-id-for-tests",
                "GOOGLE_CLIENT_SECRET": "client-secret-for-tests",
                "GOOGLE_REDIRECT_URI": "http://localhost/auth/google/callback",
                "SESSION_COOKIE_SECURE": False,
            },
        )
        self.client = self.app.test_client()
        self.db = connect_database(self.database_path)
        self.addCleanup(self.db.close)
        self.assertEqual(
            apply_migrations(self.db, self.app.config["MIGRATIONS_DIR"]),
            (1, 2, 3, 4, 5, 6, 7, 8, 9),
        )
        self.db.execute("INSERT INTO roles (nombre) VALUES ('Cliente')")
        self.db.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES ('Ana', 'Pérez', 'ana', 'ana@example.test', 1, 1)
            """
        )
        self.db.execute("INSERT INTO roles (nombre) VALUES ('Administrador')")
        self.db.commit()
        seed_initial_permissions(self.db)
        self.db.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES ('Beto', 'López', 'beto', 'beto@example.test', 2, 0)
            """
        )
        self.db.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES ('Carla', 'Ruiz', 'carla', 'carla@example.test', 1, 1)
            """
        )
        self.db.commit()
        self.active_user_id = 1
        self.inactive_user_id = 2
        self.unlinked_user_id = 3
        self.db.execute(
            """
            INSERT INTO identidades_google (usuario_id, emisor, subject, creado_utc)
            VALUES (?, ?, ?, ?)
            """,
            (self.active_user_id, GOOGLE_ISSUER, "google-sub-linked", self.now()),
        )
        self.db.commit()

    @staticmethod
    def now():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def callback(self, token, provider_error=None):
        fake_client = Mock()
        if provider_error:
            fake_client.authorize_access_token.side_effect = provider_error
        else:
            fake_client.authorize_access_token.return_value = token
        with patch(
            "backend.fitpath.auth.routes.get_oauth"
        ):
            from backend.fitpath.auth.routes import get_oauth

            get_oauth().create_client = Mock(return_value=fake_client)
            with self.client.session_transaction() as session:
                session["google_oidc_nonce"] = "nonce-for-callback"
            response = self.client.get("/auth/google/callback")
        return response, fake_client

    def valid_token(self, subject="google-sub-linked", email="ana@example.test", nonce=None):
        return {
            "userinfo": {
                "iss": GOOGLE_ISSUER,
                "sub": subject,
                "email": email,
                "nonce": nonce or "nonce-for-callback",
            }
        }

    def test_login_screen_has_real_google_route_and_static_brand_style(self):
        response = self.client.get("/auth/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Continuar con Google", response.data)
        self.assertIn(b"/auth/google/login", response.data)
        self.assertIn(b'/auth/static/js/auth-session.js?v=m11-state-2', response.data)
        self.assertIn(
            b'id="google-login-link" class="button button-primary button-full" href="/auth/google/login">',
            response.data,
        )
        self.assertIn(b'id="authenticated-session" class="auth-form" aria-live="polite" hidden', response.data)
        self.assertIn(b'id="logout-button"', response.data)
        self.assertNotIn(b"ID FitPath", response.data)
        self.assertNotIn(b"Ana", response.data)
        self.assertIn(b"No hay una sesi\xc3\xb3n activa", response.data)
        self.assertIn("no-store", response.headers["Cache-Control"])
        script = self.client.get("/auth/static/js/auth-session.js?v=m11-state-2")
        self.assertEqual(script.status_code, 200)
        self.assertIn(b'method: "POST"', script.data)
        self.assertIn(b'"/auth/logout"', script.data)
        self.assertIn(b'fetch("/auth/me"', script.data)
        self.assertIn(b"verification.status !== 401", script.data)
        script.close()
        css = self.client.get("/auth/static/css/fitpath.css")
        self.assertEqual(css.status_code, 200)
        self.assertIn(b"[hidden] { display: none !important; }", css.data)
        css.close()

    def test_login_and_logout_state_uses_the_same_me_identity(self):
        self.callback(self.valid_token())

        identity = self.client.get("/auth/me")
        self.assertEqual(identity.status_code, 200)
        self.assertEqual(
            set(identity.json), {"authenticated", "csrf_token", "user"}
        )
        self.assertEqual(
            set(identity.json["user"]), {"id", "nombre", "apellido", "rol"}
        )
        self.assertTrue(identity.json["authenticated"])
        self.assertEqual(identity.json["user"]["id"], self.active_user_id)
        self.assertEqual(identity.json["user"]["rol"], "Cliente")
        self.assertTrue(identity.json["csrf_token"])

        page = self.client.get("/auth/login")
        self.assertEqual(page.status_code, 200)
        self.assertIn("no-store", page.headers["Cache-Control"])
        self.assertIn(b'id="authenticated-session"', page.data)
        self.assertIn(b'id="logout-button"', page.data)
        self.assertIn(b"Ana P\xc3\xa9rez", page.data)
        self.assertIn(b"Cliente", page.data)
        self.assertIn(
            f"(ID FitPath {self.active_user_id})".encode(), page.data
        )
        self.assertIn(b'id="client-home-link"', page.data)
        self.assertNotIn(
            b'id="authenticated-session" class="auth-form" aria-live="polite" hidden',
            page.data,
        )
        self.assertIn(
            b'id="google-login-link" class="button button-primary button-full" href="/auth/google/login" hidden',
            page.data,
        )

        logout = self.client.post(
            "/auth/logout", data={"csrf_token": identity.json["csrf_token"]}
        )
        self.assertEqual(logout.status_code, 302)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

        logged_out_page = self.client.get("/auth/login")
        self.assertEqual(logged_out_page.status_code, 200)
        self.assertIn(b"Continuar con Google", logged_out_page.data)
        self.assertIn(
            b'id="authenticated-session" class="auth-form" aria-live="polite" hidden',
            logged_out_page.data,
        )
        self.assertIn(
            b'id="google-login-link" class="button button-primary button-full" href="/auth/google/login">',
            logged_out_page.data,
        )
        self.assertNotIn(b"Ana P\xc3\xa9rez", logged_out_page.data)
        self.assertNotIn(b"ID FitPath", logged_out_page.data)

    def test_client_home_protects_demo_views_and_serves_navigation_assets(self):
        self.assertEqual(self.client.get("/auth/cliente").status_code, 302)
        self.assertEqual(
            self.client.get("/templates/cliente/inicio/resumen.html").status_code,
            302,
        )

        login, _ = self.callback(self.valid_token())
        self.assertEqual(login.status_code, 302)
        self.assertEqual(login.location, "/auth/cliente")

        dashboard = self.client.get(login.location)
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.mimetype, "text/html")
        self.assertIn(b"experiencia de muestra", dashboard.data)
        self.assertIn("private", dashboard.headers["Cache-Control"])
        self.assertIn("no-store", dashboard.headers["Cache-Control"])
        dashboard.close()

        self.assertEqual(len(CLIENT_VIEW_PATHS), 13)
        linked_paths = set()
        for relative_path in CLIENT_VIEW_PATHS:
            page = self.client.get(f"/templates/cliente/{relative_path}")
            self.assertEqual(page.status_code, 200, relative_path)
            self.assertEqual(page.mimetype, "text/html", relative_path)
            self.assertIn(b"fictic", page.data.lower(), relative_path)
            for value in re.findall(r'(?:href|src)="([^"]+)"', page.get_data(as_text=True)):
                path = urlsplit(value).path
                if path.startswith(("/templates/cliente/", "/templates/landing.html", "/statics/")):
                    linked_paths.add(path)
            page.close()

        for path in sorted(linked_paths):
            resource = self.client.get(path)
            self.assertEqual(resource.status_code, 200, path)
            if path.endswith(".js") or path.endswith(".css"):
                self.assertIn("no-cache", resource.headers["Cache-Control"], path)
            resource.close()

        for path in (
            "/statics/js/data/cliente-demo.js",
            "/statics/js/modules/navigation-drawer.js",
        ):
            resource = self.client.get(path)
            self.assertEqual(resource.status_code, 200, path)
            resource.close()

        shell = self.client.get("/statics/js/modules/cliente-shell.js")
        self.assertEqual(shell.status_code, 200)
        self.assertIn(b'fetch("/auth/me"', shell.data)
        self.assertIn(b'fetch("/auth/logout"', shell.data)
        self.assertIn(b"Cerrar sesi", shell.data)
        shell.close()

        identity = self.client.get("/auth/me")
        self.assertEqual(identity.status_code, 200)
        logout = self.client.post(
            "/auth/logout", data={"csrf_token": identity.json["csrf_token"]}
        )
        self.assertEqual(logout.status_code, 302)
        self.assertEqual(logout.location, "/auth/login?logout=1")
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.assertEqual(self.client.get("/auth/cliente").status_code, 302)
        for relative_path in CLIENT_VIEW_PATHS:
            denied = self.client.get(f"/templates/cliente/{relative_path}")
            self.assertEqual(denied.status_code, 302, relative_path)
            self.assertEqual(denied.location, "/auth/login")

    def test_client_home_rejects_non_client_role(self):
        self.db.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES ('Dora', 'Demo', 'dora-admin', 'dora@example.test', 2, 1)
            """
        )
        self.db.commit()
        with self.client.session_transaction() as session:
            session["fitpath_user_id"] = 4
            session["csrf_token"] = "test-csrf-for-admin"

        self.assertEqual(self.client.get("/auth/cliente").status_code, 403)
        self.assertEqual(
            self.client.get("/templates/cliente/inicio/resumen.html").status_code,
            403,
        )

    def test_client_home_requires_persisted_permission(self):
        self.callback(self.valid_token())
        self.db.execute("DELETE FROM rol_permiso")
        self.db.commit()

        self.assertEqual(self.client.get("/auth/cliente").status_code, 403)
        self.assertEqual(
            self.client.get("/templates/cliente/inicio/resumen.html").status_code,
            403,
        )

    def test_provider_uses_google_oidc_discovery_and_env_credentials(self):
        from backend.fitpath.auth import GOOGLE_DISCOVERY_URL, get_oauth

        with self.app.app_context():
            provider = get_oauth().create_client("google")
            self.assertEqual(provider.client_id, "client-id-for-tests")
            self.assertEqual(provider._server_metadata_url, GOOGLE_DISCOVERY_URL)
        self.assertTrue(BaseConfig.SESSION_COOKIE_SECURE)

    def test_factory_prefers_flask_secret_key_and_supports_legacy_name(self):
        common_config = {
            "DATABASE": str(self.database_path.parent / "secret-config.sqlite3"),
            "GOOGLE_CLIENT_ID": "client-id-for-tests",
            "GOOGLE_CLIENT_SECRET": "client-secret-for-tests",
        }
        with patch.dict(
            os.environ,
            {
                "FLASK_SECRET_KEY": "prefixed-test-key",
                "SECRET_KEY": "legacy-test-key",
            },
        ):
            prefixed_app = create_app("testing", common_config)
        self.assertEqual(prefixed_app.config["SECRET_KEY"], "prefixed-test-key")

        with patch.dict(
            os.environ,
            {"FLASK_SECRET_KEY": "", "SECRET_KEY": "legacy-test-key"},
        ):
            legacy_app = create_app("testing", common_config)
        self.assertEqual(legacy_app.config["SECRET_KEY"], "legacy-test-key")

    def test_missing_google_configuration_fails_closed(self):
        app = create_app(
            "testing",
            {
                "DATABASE": str(self.database_path.parent / "unconfigured.sqlite3"),
                "SECRET_KEY": None,
                "GOOGLE_CLIENT_ID": None,
                "GOOGLE_CLIENT_SECRET": None,
            },
        )
        response = app.test_client().get("/auth/google/login")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"secret", response.data.lower())

    def test_login_starts_authorization_code_flow_with_nonce(self):
        fake_client = Mock()
        fake_client.authorize_redirect.return_value = (
            "redirect-to-google",
            302,
            {"Location": "https://accounts.google.com/o/oauth2/v2/auth?state=opaque"},
        )
        with patch(
            "backend.fitpath.auth.routes.get_oauth"
        ):
            from backend.fitpath.auth.routes import get_oauth

            get_oauth().create_client = Mock(return_value=fake_client)
            response = self.client.get("/auth/google/login")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.startswith("https://accounts.google.com/"))
        args, kwargs = fake_client.authorize_redirect.call_args
        self.assertEqual(args[0], "http://localhost/auth/google/callback")
        self.assertTrue(kwargs["nonce"])
        with self.client.session_transaction() as session:
            self.assertEqual(session["google_oidc_nonce"], kwargs["nonce"])

    def test_callback_rejects_authlib_state_mismatch(self):
        with self.assertLogs(self.app.logger.name, level="WARNING") as logs:
            response, fake_client = self.callback(
                None, MismatchingStateError(error="mismatching_state")
            )
        self.assertEqual(response.status_code, 400)
        fake_client.authorize_access_token.assert_called_once_with()
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.assertIn("stage=token_exchange_or_oidc_validation", logs.output[0])
        self.assertIn("error=MismatchingStateError", logs.output[0])
        self.assertIn("oauth_code=mismatching_state", logs.output[0])

    def test_callback_logs_missing_session_nonce_without_sensitive_data(self):
        with self.assertLogs(self.app.logger.name, level="WARNING") as logs:
            response = self.client.get(
                "/auth/google/callback?code=private-code&state=private-state"
            )
        self.assertEqual(response.status_code, 400)
        message = "\n".join(logs.output)
        self.assertIn("stage=session_nonce", message)
        self.assertIn("oauth_code=unavailable", message)
        self.assertNotIn("private-code", message)
        self.assertNotIn("private-state", message)

    def test_callback_rejects_nonce_mismatch(self):
        response, _ = self.callback(self.valid_token(nonce="wrong-nonce"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_callback_rejects_invalid_or_expired_id_token_claims_through_authlib(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_pem = private_key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        )
        private_pem = private_key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        )
        public_jwk = RSAKey.import_key(
            public_pem, {"kid": "test-key", "use": "sig"}
        ).as_dict()
        private_jwk = RSAKey.import_key(private_pem, {"kid": "test-key", "use": "sig"})
        now = int(datetime.now(timezone.utc).timestamp())
        claims = {
            "iss": GOOGLE_ISSUER,
            "aud": "client-id-for-tests",
            "sub": "google-sub-linked",
            "iat": now,
            "exp": now + 120,
            "nonce": "nonce-for-callback",
        }
        signed = jwt.encode({"alg": "RS256", "kid": "test-key"}, claims, private_jwk)

        # La prueba llama al parser OIDC de Authlib; nunca implementa JWT propio.
        with self.app.test_request_context("/auth/google/callback"):
            from backend.fitpath.auth import get_oauth

            client = get_oauth().create_client("google")
            client.load_server_metadata = lambda: {
                "issuer": GOOGLE_ISSUER,
                "id_token_signing_alg_values_supported": ["RS256"],
            }
            client.fetch_jwk_set = lambda force=False: {"keys": [public_jwk]}
            parsed = client.parse_id_token({"id_token": signed}, nonce="nonce-for-callback")
            self.assertEqual(parsed["sub"], "google-sub-linked")

            with self.assertRaises(Exception):
                client.parse_id_token({"id_token": signed}, nonce="wrong-nonce")

            expired_claims = dict(claims, exp=now - 300, iat=now - 400)
            expired = jwt.encode(
                {"alg": "RS256", "kid": "test-key"}, expired_claims, private_jwk
            )
            with self.assertRaises(Exception):
                client.parse_id_token({"id_token": expired}, nonce="nonce-for-callback")

            other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            other_private_pem = other_private_key.private_bytes(
                Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
            )
            other_private_jwk = RSAKey.import_key(
                other_private_pem, {"kid": "test-key", "use": "sig"}
            )
            invalid_signature = jwt.encode(
                {"alg": "RS256", "kid": "test-key"}, claims, other_private_jwk
            )
            with self.assertRaises(Exception):
                client.parse_id_token(
                    {"id_token": invalid_signature}, nonce="nonce-for-callback"
                )

    def test_unlinked_identity_never_matches_by_email_and_creates_opaque_request(self):
        response, _ = self.callback(
            self.valid_token(subject="unlinked-google-sub", email="ana@example.test")
        )
        self.assertEqual(response.status_code, 403)
        reference = response.data.decode("utf-8").split("<code>", 1)[1].split("</code>", 1)[0]
        row = self.db.execute(
            "SELECT * FROM solicitudes_vinculo_google WHERE subject = ?",
            ("unlinked-google-sub",),
        ).fetchone()
        self.assertEqual(hashlib.sha256(reference.encode()).hexdigest(), row["referencia_sha256"])
        self.assertNotIn(reference, row["referencia_sha256"])
        self.assertIsNone(
            self.db.execute(
                "SELECT id_identidad FROM identidades_google WHERE subject = ?",
                ("unlinked-google-sub",),
            ).fetchone()
        )
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_inactive_linked_user_is_denied(self):
        self.db.execute(
            """
            INSERT INTO identidades_google (usuario_id, emisor, subject, creado_utc)
            VALUES (?, ?, ?, ?)
            """,
            (self.inactive_user_id, GOOGLE_ISSUER, "inactive-sub", self.now()),
        )
        self.db.commit()
        response, _ = self.callback(self.valid_token(subject="inactive-sub"))
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"desactivada", response.data)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_successful_login_creates_fitpath_session_and_uses_database_role(self):
        response, _ = self.callback(self.valid_token())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/auth/cliente")
        identity = self.client.get("/auth/me")
        self.assertEqual(identity.status_code, 200)
        self.assertEqual(identity.json["user"]["id"], self.active_user_id)
        self.assertEqual(identity.json["user"]["rol"], "Cliente")
        self.assertTrue(identity.json["csrf_token"])
        self.assertTrue(self.app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(self.app.config["SESSION_COOKIE_SAMESITE"], "Lax")
        with self.client.session_transaction() as session:
            self.assertEqual(session["fitpath_user_id"], self.active_user_id)
            self.assertNotIn("rol", session)

    def test_logout_requires_csrf_and_clears_session(self):
        self.callback(self.valid_token())
        authenticated_page = self.client.get("/auth/login")
        self.assertIn(b'id="authenticated-session"', authenticated_page.data)
        self.assertIn(b"Cerrar sesi\xc3\xb3n", authenticated_page.data)
        self.assertEqual(self.client.get("/auth/logout").status_code, 405)
        self.assertEqual(self.client.post("/auth/logout").status_code, 400)
        with self.client.session_transaction() as session:
            csrf_token = session["csrf_token"]
        response = self.client.post("/auth/logout", data={"csrf_token": csrf_token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/auth/login?logout=1")
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        logged_out_page = self.client.get(response.location)
        self.assertIn(b"Sesi\xc3\xb3n cerrada correctamente", logged_out_page.data)
        self.assertIn(
            b'id="authenticated-session" class="auth-form" aria-live="polite" hidden',
            logged_out_page.data,
        )

    def test_rotating_secret_key_invalidates_flask_cookie_session(self):
        self.callback(self.valid_token())
        self.assertEqual(self.client.get("/auth/me").status_code, 200)
        self.app.config["SECRET_KEY"] = "a-different-test-secret-after-restart"
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        login_page = self.client.get("/auth/login")
        self.assertIn(
            b'id="authenticated-session" class="auth-form" aria-live="polite" hidden',
            login_page.data,
        )
        self.assertIn(b"No hay una sesi\xc3\xb3n activa", login_page.data)

    def test_expired_flask_session_is_not_authenticated(self):
        self.app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(seconds=-1)
        with self.client.session_transaction() as session:
            session.permanent = True
            session["fitpath_user_id"] = self.active_user_id
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_user_role_cannot_be_changed_by_session_or_callback(self):
        response, _ = self.callback(self.valid_token())
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            session["rol"] = "Administrador"
            session["usuario_id"] = self.inactive_user_id
        identity = self.client.get("/auth/me")
        self.assertEqual(identity.json["user"]["id"], self.active_user_id)
        self.assertEqual(identity.json["user"]["rol"], "Cliente")
        db_user = self.db.execute(
            "SELECT rol_id FROM usuarios WHERE id_usuario = ?", (self.active_user_id,)
        ).fetchone()
        self.assertEqual(db_user["rol_id"], 1)

    def test_local_provisioning_requires_approval_active_user_and_unexpired_code(self):
        unlinked_response, _ = self.callback(
            self.valid_token(subject="linkable-google-sub", email="different@example.test")
        )
        reference = (
            unlinked_response.data.decode("utf-8")
            .split("<code>", 1)[1]
            .split("</code>", 1)[0]
        )
        self.assertFalse(approve_link(self.db, reference, self.inactive_user_id))
        self.assertTrue(approve_link(self.db, reference, self.unlinked_user_id))
        self.assertFalse(approve_link(self.db, reference, self.unlinked_user_id))
        login_response, _ = self.callback(
            self.valid_token(subject="linkable-google-sub", email="different@example.test")
        )
        self.assertEqual(login_response.status_code, 302)

        second_response, _ = self.callback(self.valid_token(subject="expired-google-sub"))
        expired_reference = (
            second_response.data.decode("utf-8")
            .split("<code>", 1)[1]
            .split("</code>", 1)[0]
        )
        future_now = datetime.now(timezone.utc) + timedelta(hours=1)
        self.assertFalse(
            approve_link(
                self.db, expired_reference, self.active_user_id, now=future_now
            )
        )

    def test_demo_provisioner_creates_one_client_profile_without_google_link(self):
        before_users = self.db.execute("SELECT count(*) FROM usuarios").fetchone()[0]
        before_permissions = self.db.execute("SELECT count(*) FROM rol_permiso").fetchone()[0]
        user_id, created = create_demo_client(self.db)
        repeated_id, created_again = create_demo_client(self.db)

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(repeated_id, user_id)
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM usuarios").fetchone()[0],
            before_users + 1,
        )
        user = self.db.execute(
            "SELECT rol_id, activo FROM usuarios WHERE id_usuario = ?", (user_id,)
        ).fetchone()
        self.assertEqual(tuple(user), (1, 1))
        self.assertIsNotNone(
            self.db.execute(
                "SELECT id_cliente FROM clientes WHERE usuario_id = ?", (user_id,)
            ).fetchone()
        )
        self.assertIsNone(
            self.db.execute(
                "SELECT id_identidad FROM identidades_google WHERE usuario_id = ?",
                (user_id,),
            ).fetchone()
        )
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM rol_permiso").fetchone()[0],
            before_permissions,
        )

    def test_local_client_provisioner_is_transactional_and_idempotent(self):
        data = {
            "nombre": "Cliente",
            "apellido": "Prueba",
            "nombre_usuario": "client1",
            "email": "client1@fitpath.test",
        }
        user_id, created = create_local_client(self.db, **data)
        repeated_id, created_again = create_local_client(self.db, **data)

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(repeated_id, user_id)
        user = self.db.execute(
            "SELECT nombre, apellido, nombre_usuario, email, rol_id, activo "
            "FROM usuarios WHERE id_usuario = ?",
            (user_id,),
        ).fetchone()
        self.assertEqual(tuple(user), (*data.values(), 1, 1))
        self.assertIsNotNone(
            self.db.execute(
                "SELECT id_cliente FROM clientes WHERE usuario_id = ?", (user_id,)
            ).fetchone()
        )
        self.assertIsNone(
            self.db.execute(
                "SELECT id_identidad FROM identidades_google WHERE usuario_id = ?",
                (user_id,),
            ).fetchone()
        )

    def test_migration_enforces_unique_identity_user_and_foreign_key(self):
        with self.assertRaises(Exception):
            self.db.execute(
                """
                INSERT INTO identidades_google (usuario_id, emisor, subject, creado_utc)
                VALUES (?, ?, ?, ?)
                """,
                (self.inactive_user_id, GOOGLE_ISSUER, "google-sub-linked", self.now()),
            )
        with self.assertRaises(Exception):
            self.db.execute(
                """
                INSERT INTO identidades_google (usuario_id, emisor, subject, creado_utc)
                VALUES (?, ?, ?, ?)
                """,
                (self.active_user_id, GOOGLE_ISSUER, "other-google-sub", self.now()),
            )
        with self.assertRaises(Exception):
            self.db.execute(
                """
                INSERT INTO identidades_google (usuario_id, emisor, subject, creado_utc)
                VALUES (?, ?, ?, ?)
                """,
                (999, GOOGLE_ISSUER, "missing-user-sub", self.now()),
            )
        self.db.rollback()
        self.assertEqual(self.db.execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
