import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.fitpath import create_app
from backend.fitpath.database import connect_database
from backend.fitpath.demo_data import DEMO_USERS, seed_full_demo
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.seeds import (
    seed_initial_currencies,
    seed_initial_permissions,
    seed_initial_roles,
)


class DemoDataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database_path = Path(temporary.name) / "demo.sqlite3"
        self.app = create_app(
            "testing",
            {
                "DATABASE": str(self.database_path),
                "SECRET_KEY": "demo-data-test-secret",
            },
        )
        self.db = connect_database(self.database_path)
        self.addCleanup(self.db.close)
        apply_migrations(self.db, self.app.config["MIGRATIONS_DIR"])
        seed_initial_roles(self.db)
        seed_initial_permissions(self.db)
        seed_initial_currencies(self.db)

    def test_seed_requires_confirmation_and_is_reproducible(self):
        with self.assertRaises(ValueError):
            seed_full_demo(self.db)

        timestamp = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)
        first = seed_full_demo(self.db, confirmed=True, now=timestamp)
        second = seed_full_demo(self.db, confirmed=True, now=timestamp)

        self.assertEqual(first, second)
        self.assertEqual(set(first["users"]), set(DEMO_USERS))
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM usuarios WHERE nombre_usuario LIKE 'demo.%'"
            ).fetchone()[0],
            5,
        )
        self.assertEqual(self.db.execute("SELECT count(*) FROM clases").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM rutinas").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM progresos").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM deudas").fetchone()[0], 1)
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM identidades_google").fetchone()[0], 0
        )
        self.assertEqual(self.db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_demo_login_is_local_explicit_and_disabled_by_default(self):
        timestamp = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)
        seed_full_demo(self.db, confirmed=True, now=timestamp)
        disabled_client = self.app.test_client()
        self.assertEqual(
            disabled_client.post("/auth/demo-login/client").status_code, 404
        )

        enabled_app = create_app(
            "testing",
            {
                "DATABASE": str(self.database_path),
                "SECRET_KEY": "enabled-demo-login-test-secret",
                "DEMO_LOGIN_ENABLED": True,
            },
        )
        enabled_client = enabled_app.test_client()
        targets = {
            "client": "/auth/cliente",
            "trainer": "/auth/entrenador",
            "manager": "/auth/jefe-sede",
            "admin": "/auth/administrador",
            "technician": "/auth/tecnico",
        }
        for slug, target in targets.items():
            response = enabled_client.post(f"/auth/demo-login/{slug}")
            self.assertEqual(response.status_code, 302, slug)
            self.assertEqual(response.location, target, slug)
            identity = enabled_client.get("/auth/me")
            self.assertEqual(identity.status_code, 200, slug)
            self.assertTrue(identity.json["csrf_token"])

        self.assertEqual(
            enabled_client.post(
                "/auth/demo-login/client",
                environ_base={"REMOTE_ADDR": "203.0.113.4"},
            ).status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
