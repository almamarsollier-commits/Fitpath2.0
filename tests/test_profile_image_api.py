"""Pruebas locales de la imagen de perfil privada, sin acceder a AWS."""

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.fitpath import create_app
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.seeds import seed_initial_permissions, seed_initial_roles
from backend.fitpath.services.s3_storage import StorageOperationError


PNG_IMAGE = b"\x89PNG\r\n\x1a\n" + b"profile-image"


class FakeProfileStorage:
    def __init__(self):
        self.settings = SimpleNamespace(
            prefix="fitpath", max_upload_bytes=5 * 1024 * 1024, download_ttl_seconds=300
        )
        self.uploads = []
        self.deleted = []
        self.fail_upload = False
        self.fail_download = False

    def upload_private(
        self, file_object, *, namespace, content_type, content_length=None
    ):
        if self.fail_upload:
            raise StorageOperationError("simulated")
        content = file_object.read()
        self.uploads.append((content, namespace, content_type, content_length))
        return f"fitpath/{namespace}/new-profile-image"

    def create_download_url(self, object_key):
        if self.fail_download:
            raise StorageOperationError("simulated")
        return f"https://private.example.test/{object_key}?temporary=1"

    def delete_private(self, object_key):
        self.deleted.append(object_key)


class ProfileImageApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "profile.sqlite3"
        self.app = self._create_app()
        self.client = self.app.test_client()
        self.db = connect_database(self.database_path)
        self.addCleanup(self.db.close)
        self.assertEqual(
            apply_migrations(self.db, self.app.config["MIGRATIONS_DIR"]),
            (1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
        )
        seed_initial_roles(self.db)
        seed_initial_permissions(self.db)
        self.client_user_id = self._create_user("Cliente", "client-profile")
        self.admin_user_id = self._create_user("Administrador", "admin-profile")
        self.client_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (self.client_user_id,)
        ).lastrowid
        self.db.commit()
        self.storage = FakeProfileStorage()

    def _create_app(self):
        return create_app(
            "testing",
            {
                "DATABASE": str(self.database_path),
                "SECRET_KEY": "profile-image-test-only",
                "SESSION_COOKIE_SECURE": False,
            },
        )

    def _create_user(self, role, username):
        role_id = self.db.execute(
            "SELECT id_rol FROM roles WHERE nombre = ?", (role,)
        ).fetchone()[0]
        return self.db.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES ('Perfil', 'Prueba', ?, ?, ?, 1)
            """,
            (username, f"{username}@example.test", role_id),
        ).lastrowid

    def _login(self, user_id=None, csrf_token="profile-csrf"):
        with self.client.session_transaction() as session:
            session["fitpath_user_id"] = user_id or self.client_user_id
            session["csrf_token"] = csrf_token

    def _upload(self, content=PNG_IMAGE, content_type="image/png", csrf="profile-csrf"):
        return self.client.post(
            "/api/v1/client/profile-image",
            data={"image": (io.BytesIO(content), "profile.png", content_type)},
            headers={"X-CSRF-Token": csrf},
            content_type="multipart/form-data",
        )

    def test_authentication_role_permission_and_csrf_are_required(self):
        self.assertEqual(self.client.get("/api/v1/client/profile-image").status_code, 401)

        self._login(self.admin_user_id)
        self.assertEqual(self.client.get("/api/v1/client/profile-image").status_code, 403)

        self._login()
        with patch(
            "backend.fitpath.api.v1.profile.get_s3_storage", return_value=self.storage
        ):
            response = self._upload(csrf="wrong-token")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"], "csrf_failed")
        self.assertEqual(self.storage.uploads, [])

    def test_upload_validates_real_mime_persists_key_and_returns_temporary_url(self):
        self._login()
        with patch(
            "backend.fitpath.api.v1.profile.get_s3_storage", return_value=self.storage
        ):
            response = self._upload()

        self.assertEqual(response.status_code, 201)
        self.assertIn("temporary=1", response.json["image"]["url"])
        self.assertEqual(
            self.storage.uploads,
            [(PNG_IMAGE, f"clientes/{self.client_id}/perfil", "image/png", len(PNG_IMAGE))],
        )
        stored = self.db.execute(
            "SELECT imagen_perfil_clave_s3 FROM clientes WHERE id_cliente = ?",
            (self.client_id,),
        ).fetchone()[0]
        self.assertEqual(stored, f"fitpath/clientes/{self.client_id}/perfil/new-profile-image")

    def test_declared_mime_must_match_image_signature(self):
        self._login()
        with patch(
            "backend.fitpath.api.v1.profile.get_s3_storage", return_value=self.storage
        ):
            mismatch = self._upload(content_type="image/jpeg")
            executable = self._upload(content=b"MZ-not-an-image", content_type="image/png")

        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(executable.status_code, 400)
        self.assertEqual(self.storage.uploads, [])

    def test_only_the_authenticated_client_reference_can_be_read(self):
        self._login()
        self.db.execute(
            "UPDATE clientes SET imagen_perfil_clave_s3 = ? WHERE id_cliente = ?",
            (f"fitpath/clientes/{self.client_id}/perfil/existing", self.client_id),
        )
        self.db.commit()
        with patch(
            "backend.fitpath.api.v1.profile.get_s3_storage", return_value=self.storage
        ):
            response = self.client.get("/api/v1/client/profile-image")
        self.assertEqual(response.status_code, 200)
        self.assertIn("temporary=1", response.json["image"]["url"])

        self.db.execute(
            "UPDATE clientes SET imagen_perfil_clave_s3 = ? WHERE id_cliente = ?",
            ("fitpath/clientes/999/perfil/foreign", self.client_id),
        )
        self.db.commit()
        with patch(
            "backend.fitpath.api.v1.profile.get_s3_storage", return_value=self.storage
        ):
            invalid = self.client.get("/api/v1/client/profile-image")
        self.assertEqual(invalid.status_code, 500)
        self.assertEqual(invalid.json["error"], "profile_image_reference_invalid")

    def test_aws_errors_do_not_persist_a_reference(self):
        self._login()
        self.storage.fail_upload = True
        with patch(
            "backend.fitpath.api.v1.profile.get_s3_storage", return_value=self.storage
        ):
            response = self._upload()
        self.assertEqual(response.status_code, 503)
        stored = self.db.execute(
            "SELECT imagen_perfil_clave_s3 FROM clientes WHERE id_cliente = ?",
            (self.client_id,),
        ).fetchone()[0]
        self.assertIsNone(stored)

    def test_replacement_deletes_only_the_authenticated_client_old_object(self):
        self._login()
        own_key = f"fitpath/clientes/{self.client_id}/perfil/old"
        self.db.execute(
            "UPDATE clientes SET imagen_perfil_clave_s3 = ? WHERE id_cliente = ?",
            (own_key, self.client_id),
        )
        self.db.commit()
        with patch(
            "backend.fitpath.api.v1.profile.get_s3_storage", return_value=self.storage
        ):
            self.assertEqual(self._upload().status_code, 201)
        self.assertEqual(self.storage.deleted, [own_key])

        foreign_key = "fitpath/clientes/999/perfil/foreign"
        self.db.execute(
            "UPDATE clientes SET imagen_perfil_clave_s3 = ? WHERE id_cliente = ?",
            (foreign_key, self.client_id),
        )
        self.db.commit()
        with patch(
            "backend.fitpath.api.v1.profile.get_s3_storage", return_value=self.storage
        ):
            self.assertEqual(self._upload().status_code, 201)
        self.assertNotIn(foreign_key, self.storage.deleted)

    def test_reference_survives_a_flask_restart(self):
        self._login()
        with patch(
            "backend.fitpath.api.v1.profile.get_s3_storage", return_value=self.storage
        ):
            self.assertEqual(self._upload().status_code, 201)

        restarted_app = self._create_app()
        restarted_client = restarted_app.test_client()
        with restarted_client.session_transaction() as session:
            session["fitpath_user_id"] = self.client_user_id
            session["csrf_token"] = "restarted-csrf"
        restarted_storage = FakeProfileStorage()
        with patch(
            "backend.fitpath.api.v1.profile.get_s3_storage",
            return_value=restarted_storage,
        ):
            response = restarted_client.get("/api/v1/client/profile-image")
        self.assertEqual(response.status_code, 200)
        self.assertIn("new-profile-image", response.json["image"]["url"])


if __name__ == "__main__":
    unittest.main()
