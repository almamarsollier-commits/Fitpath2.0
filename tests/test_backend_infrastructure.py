"""Pruebas de infraestructura Flask y SQLite sin tablas de negocio."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.fitpath import create_app
from backend.fitpath.database import (
    DatabaseConfigurationError,
    connect_database,
    get_db,
)
from backend.fitpath.migrations import MigrationError, apply_migrations


class BackendInfrastructureTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def create_testing_app(self, database_path):
        return create_app(
            "testing",
            {"DATABASE": str(database_path)},
        )

    def test_factory_separates_environments_and_registers_auth_and_client_routes(self):
        default_development_app = create_app("development")
        default_testing_app = create_app("testing")
        self.assertNotEqual(
            Path(default_development_app.config["DATABASE"]).resolve(),
            Path(default_testing_app.config["DATABASE"]).resolve(),
        )

        development_database = self.root / "development" / "fitpath.sqlite3"
        testing_database = self.root / "testing" / "fitpath.sqlite3"

        development_app = create_app(
            "development",
            {"DATABASE": str(development_database)},
        )
        testing_app = self.create_testing_app(testing_database)

        self.assertNotEqual(
            Path(development_app.config["DATABASE"]).resolve(),
            Path(testing_app.config["DATABASE"]).resolve(),
        )
        self.assertTrue(testing_app.config["TESTING"])
        self.assertEqual(
            {rule.rule for rule in testing_app.url_map.iter_rules()},
            {
                "/auth/static/<path:filename>",
                "/auth/login",
                "/auth/google/login",
                "/auth/google/callback",
                "/auth/demo-login/<role_slug>",
                "/auth/me",
                "/auth/logout",
                "/auth/cliente",
                "/auth/entrenador",
                "/auth/jefe-sede",
                "/auth/administrador",
                "/auth/tecnico",
                "/auth/profile",
                "/templates/cliente/<path:filename>",
                "/templates/landing.html",
                "/statics/<path:filename>",
                "/api/v1/assistant/capabilities",
                "/api/v1/assistant/classes",
                "/api/v1/assistant/routine",
                "/api/v1/assistant/progress",
                "/api/v1/assistant/membership",
                "/api/v1/client/profile-image",
                "/api/v1/me/profile",
                "/api/v1/me/profile-image",
                "/api/v1/client/classes",
                "/api/v1/client/classes/<int:class_id>/enrollment",
                "/api/v1/client/enrollments",
                "/api/v1/client/routines",
                "/api/v1/client/progress",
                "/api/v1/client/dashboard",
                "/api/v1/client/payments",
                "/api/v1/client/memberships",
                "/api/v1/client/memberships/<int:membership_id>/select",
                "/api/v1/client/payment-intents",
                "/api/v1/client/payment-intents/confirm",
                "/api/v1/payments/mercado-pago/webhook",
                "/api/v1/trainer/dashboard",
                "/api/v1/trainer/routines",
                "/api/v1/trainer/routines/<int:routine_id>",
                "/api/v1/trainer/exercises",
                "/api/v1/trainer/exercises/<int:exercise_id>",
                "/api/v1/trainer/routines/<int:routine_id>/exercises",
                "/api/v1/trainer/attendance",
                "/api/v1/trainer/availability",
                "/api/v1/trainer/availability/<int:availability_id>",
                "/api/v1/manager/dashboard",
                "/api/v1/manager/personnel/<int:user_id>",
                "/api/v1/manager/activities",
                "/api/v1/manager/activities/<int:activity_id>",
                "/api/v1/manager/classes",
                "/api/v1/manager/classes/<int:class_id>",
                "/api/v1/admin/dashboard",
                "/api/v1/admin/reports",
                "/api/v1/admin/users",
                "/api/v1/admin/users/<int:user_id>",
                "/api/v1/admin/sites",
                "/api/v1/admin/sites/<int:site_id>",
                "/api/v1/admin/activities",
                "/api/v1/admin/activities/<int:activity_id>",
                "/api/v1/admin/memberships",
                "/api/v1/admin/memberships/<int:membership_id>",
                "/api/v1/admin/permissions",
                "/api/v1/admin/roles/<int:role_id>/permissions",
                "/api/v1/technician/dashboard",
                "/api/v1/technician/tickets",
                "/api/v1/technician/tickets/<int:ticket_id>",
                "/api/v1/technician/machines/<int:machine_id>",
            },
        )
        self.assertFalse(development_database.exists())
        self.assertFalse(testing_database.exists())

    def test_connection_enables_and_enforces_foreign_keys(self):
        app = self.create_testing_app(self.root / "fk" / "fitpath.sqlite3")

        with app.app_context():
            connection = get_db()
            self.assertEqual(
                connection.execute("PRAGMA foreign_keys").fetchone()[0],
                1,
            )
            connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            connection.execute(
                """
                CREATE TABLE child (
                    parent_id INTEGER NOT NULL REFERENCES parent(id)
                )
                """
            )

            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO child (parent_id) VALUES (?)", (99,))

            self.assertEqual(
                connection.execute("PRAGMA foreign_key_check").fetchall(),
                [],
            )

    def test_new_backend_rejects_legacy_database_path(self):
        legacy_database = Path(__file__).resolve().parents[1] / "gimnasio.db"
        existed_before = legacy_database.exists()
        with self.assertRaises(DatabaseConfigurationError):
            connect_database(legacy_database)
        self.assertEqual(legacy_database.exists(), existed_before)

    def test_migration_runs_once_and_records_its_version(self):
        database = self.root / "migration" / "fitpath.sqlite3"
        migrations = self.root / "migrations"
        migrations.mkdir()
        (migrations / "0001_create_probe.sql").write_text(
            "CREATE TABLE migration_probe (id INTEGER PRIMARY KEY);",
            encoding="utf-8",
        )

        connection = connect_database(database)
        self.addCleanup(connection.close)

        self.assertEqual(apply_migrations(connection, migrations), (1,))
        self.assertEqual(apply_migrations(connection, migrations), ())
        self.assertEqual(
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT version, name FROM schema_migrations"
                )
            ],
            [(1, "0001_create_probe.sql")],
        )
        self.assertEqual(
            connection.execute("PRAGMA foreign_keys").fetchone()[0],
            1,
        )
        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_failed_migration_rolls_back_ddl_and_registry_entry(self):
        database = self.root / "failed" / "fitpath.sqlite3"
        migrations = self.root / "failing_migrations"
        migrations.mkdir()
        (migrations / "0001_partial_then_fail.sql").write_text(
            """
            CREATE TABLE should_rollback (id INTEGER PRIMARY KEY);
            INSERT INTO missing_table (id) VALUES (1);
            """,
            encoding="utf-8",
        )

        connection = connect_database(database)
        self.addCleanup(connection.close)

        with self.assertRaises(MigrationError):
            apply_migrations(connection, migrations)

        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = ? AND name = ?",
            ("table", "should_rollback"),
        ).fetchone()
        self.assertIsNone(table)
        self.assertEqual(
            connection.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall(),
            [],
        )
        self.assertFalse(connection.in_transaction)
        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
