"""Pruebas del esquema inicial de identidad y sedes con bases temporales."""

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _file_assertions import assert_optional_file_unchanged, snapshot_optional_file
from backend.fitpath import create_app
from backend.fitpath.database import (
    DatabaseConfigurationError,
    connect_database,
    get_db,
)
from backend.fitpath.migrations import MigrationError, apply_migrations
from backend.fitpath.permissions import CLIENT_DATA_PERMISSION, CLIENT_VIEWS_PERMISSION
from backend.fitpath.seeds import (
    INITIAL_ROLES,
    seed_initial_permissions,
    seed_initial_roles,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPOSITORY_ROOT / "backend" / "fitpath" / "migrations"


class IdentitySchemaTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "identity.sqlite3"
        self.connection = connect_database(self.database_path)
        self.addCleanup(self.connection.close)
        self.assertEqual(apply_migrations(self.connection, MIGRATIONS_DIR), (1, 2, 3, 4, 5, 6, 7, 8, 9))

    def insert_role(self, name="Cliente"):
        cursor = self.connection.execute(
            "INSERT INTO roles (nombre) VALUES (?)",
            (name,),
        )
        return cursor.lastrowid

    def insert_user(self, role_id, username="ana", email="ana@example.com"):
        return self.connection.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("Ana", "Pérez", username, email, role_id),
        ).lastrowid

    def test_initial_identity_tables_remain_present_with_valid_foreign_keys(self):
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ?",
                ("table",),
            )
        }
        expected_tables = {
            "schema_migrations",
            "roles",
            "permisos",
            "rol_permiso",
            "usuarios",
            "sedes",
        }
        self.assertTrue(expected_tables.issubset(tables))
        self.assertNotIn("administradores", tables)
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_keys").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(),
            [],
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_list('usuarios')").fetchone()["table"],
            "roles",
        )
        self.assertEqual(
            {
                row["table"]
                for row in self.connection.execute(
                    "PRAGMA foreign_key_list('rol_permiso')"
                )
            },
            {"roles", "permisos"},
        )

    def test_role_catalog_is_explicit_idempotent_and_has_no_permissions(self):
        self.assertEqual(
            self.connection.execute("SELECT count(*) FROM roles").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute("SELECT count(*) FROM permisos").fetchone()[0],
            0,
        )
        self.assertEqual(seed_initial_roles(self.connection), INITIAL_ROLES)
        self.assertEqual(seed_initial_roles(self.connection), ())
        self.assertEqual(
            tuple(
                row[0]
                for row in self.connection.execute(
                    "SELECT nombre FROM roles ORDER BY id_rol"
                )
            ),
            INITIAL_ROLES,
        )
        self.assertEqual(
            self.connection.execute("SELECT count(*) FROM rol_permiso").fetchone()[0],
            0,
        )

    def test_permission_seed_assigns_client_view_and_data_permissions(self):
        seed_initial_roles(self.connection)
        self.assertEqual(
            seed_initial_permissions(self.connection),
            (CLIENT_VIEWS_PERMISSION, CLIENT_DATA_PERMISSION),
        )
        self.assertEqual(seed_initial_permissions(self.connection), ())
        assignment = self.connection.execute(
            """
            SELECT p.clave, r.nombre
            FROM rol_permiso AS rp
            JOIN permisos AS p ON p.id_permiso = rp.permiso_id
            JOIN roles AS r ON r.id_rol = rp.rol_id
            ORDER BY p.clave
            """
        ).fetchall()
        self.assertEqual(
            [tuple(row) for row in assignment],
            [
                (CLIENT_DATA_PERMISSION, "Cliente"),
                (CLIENT_VIEWS_PERMISSION, "Cliente"),
            ],
        )

    def test_user_references_existing_role_and_rejects_missing_role(self):
        role_id = self.insert_role()
        user_id = self.insert_user(role_id)
        self.assertEqual(
            self.connection.execute(
                "SELECT rol_id FROM usuarios WHERE id_usuario = ?",
                (user_id,),
            ).fetchone()[0],
            role_id,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_user(9999, username="otra", email="otra@example.com")
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(),
            [],
        )

    def test_role_permission_link_enforces_both_foreign_keys_and_pair_uniqueness(self):
        role_id = self.insert_role()
        permission_id = self.connection.execute(
            "INSERT INTO permisos (clave) VALUES (?)",
            ("clases.consultar",),
        ).lastrowid
        self.connection.execute(
            "INSERT INTO rol_permiso (rol_id, permiso_id) VALUES (?, ?)",
            (role_id, permission_id),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO rol_permiso (rol_id, permiso_id) VALUES (?, ?)",
                (role_id, permission_id),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO rol_permiso (rol_id, permiso_id) VALUES (?, ?)",
                (9999, permission_id),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO rol_permiso (rol_id, permiso_id) VALUES (?, ?)",
                (role_id, 9999),
            )

    def test_email_and_username_are_unique_and_ascii_normalized(self):
        role_id = self.insert_role()
        self.insert_user(role_id)
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_user(role_id, username="otra", email="ana@example.com")
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_user(role_id, username="ana", email="otra@example.com")
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_user(role_id, username="MARTA", email="marta@example.com")
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_user(role_id, username="marta", email="MARTA@example.com")

    def test_required_values_and_user_status_are_constrained(self):
        role_id = self.insert_role()
        invalid_roles = ("", "   ")
        for name in invalid_roles:
            with self.subTest(role_name=name), self.assertRaises(sqlite3.IntegrityError):
                self.connection.execute(
                    "INSERT INTO roles (nombre) VALUES (?)",
                    (name,),
                )

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO permisos (clave) VALUES (?)",
                ("   ",),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO usuarios
                    (nombre, apellido, nombre_usuario, email, rol_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (" ", "Pérez", "luz", "luz@example.com", role_id),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO usuarios
                    (nombre, apellido, nombre_usuario, email, rol_id, activo)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("Luz", "Pérez", "luz", "luz@example.com", role_id, 2),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO sedes (nombre, direccion, zona_horaria) VALUES (?, ?, ?)",
                ("Sede", "Dirección", " "),
            )

        user_id = self.connection.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("Luz", "Pérez", "luz", "luz@example.com", role_id, 0),
        ).lastrowid
        self.assertEqual(
            self.connection.execute(
                "SELECT activo FROM usuarios WHERE id_usuario = ?",
                (user_id,),
            ).fetchone()[0],
            0,
        )

    def test_migrations_are_idempotent_and_registry_records_all_versions(self):
        self.assertEqual(apply_migrations(self.connection, MIGRATIONS_DIR), ())
        self.assertEqual(
            tuple(
                (row["version"], row["name"])
                for row in self.connection.execute(
                    "SELECT version, name FROM schema_migrations ORDER BY version"
                )
            ),
            (
                (1, "0001_identidad_roles_permisos_sedes.sql"),
                (2, "0002_actividades_entrenadores_clases.sql"),
                (3, "0003_clientes_inscripciones_asistencias.sql"),
                (4, "0004_objetivos_rutinas.sql"),
                (5, "0005_progreso_alimentacion.sql"),
                (6, "0006_membresias_beneficios_suscripciones_pagos.sql"),
                (7, "0007_mantenimiento_perfiles.sql"),
                (8, "0008_remuneraciones.sql"),
                (9, "0009_google_identities.sql"),
            ),
        )
        self.assertEqual(
            self.connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0],
            9,
        )

    def test_altered_applied_migration_is_rejected_by_checksum(self):
        copied_migrations = self.root / "altered_migrations"
        copied_migrations.mkdir()
        original = MIGRATIONS_DIR / "0001_identidad_roles_permisos_sedes.sql"
        copied = copied_migrations / original.name
        shutil.copyfile(original, copied)
        connection = connect_database(self.root / "checksum.sqlite3")
        self.addCleanup(connection.close)
        self.assertEqual(apply_migrations(connection, copied_migrations), (1,))
        copied.write_text(
            copied.read_text(encoding="utf-8") + chr(10) + "-- checksum alterado" + chr(10),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(MigrationError, "modificada"):
            apply_migrations(connection, copied_migrations)

    def test_failed_real_migration_rolls_back_every_business_table(self):
        failing_migrations = self.root / "failing_migrations"
        failing_migrations.mkdir()
        original = MIGRATIONS_DIR / "0001_identidad_roles_permisos_sedes.sql"
        script = original.read_text(encoding="utf-8")
        script += (
            chr(10)
            + "CREATE TABLE rollback_probe (id INTEGER PRIMARY KEY);"
            + chr(10)
            + "INSERT INTO table_that_does_not_exist (id) VALUES (1);"
            + chr(10)
        )
        (failing_migrations / original.name).write_text(script, encoding="utf-8")
        connection = connect_database(self.root / "rollback.sqlite3")
        self.addCleanup(connection.close)
        with self.assertRaises(MigrationError):
            apply_migrations(connection, failing_migrations)
        business_tables = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = ? AND name NOT LIKE ?
            """,
            ("table", "sqlite_%"),
        ).fetchall()
        self.assertEqual([row[0] for row in business_tables], ["schema_migrations"])
        self.assertEqual(
            connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0],
            0,
        )
        self.assertFalse(connection.in_transaction)
        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_development_and_testing_databases_are_isolated(self):
        development_database = self.root / "development" / "fitpath.sqlite3"
        testing_database = self.root / "testing" / "fitpath.sqlite3"
        development_app = create_app(
            "development",
            {"DATABASE": str(development_database)},
        )
        testing_app = create_app(
            "testing",
            {"DATABASE": str(testing_database)},
        )
        self.assertNotEqual(
            Path(development_app.config["DATABASE"]).resolve(),
            Path(testing_app.config["DATABASE"]).resolve(),
        )

        for app in (development_app, testing_app):
            with app.app_context():
                connection = get_db()
                apply_migrations(connection, app.config["MIGRATIONS_DIR"])

        with development_app.app_context():
            connection = get_db()
            connection.execute("INSERT INTO roles (nombre) VALUES (?)", ("Prueba",))
            connection.commit()
        with testing_app.app_context():
            self.assertEqual(
                get_db().execute("SELECT count(*) FROM roles").fetchone()[0],
                0,
            )

    def test_legacy_database_metadata_is_unchanged_and_never_opened(self):
        legacy_database = REPOSITORY_ROOT / "gimnasio.db"
        before = snapshot_optional_file(legacy_database)
        with self.assertRaises(DatabaseConfigurationError):
            connect_database(legacy_database)
        assert_optional_file_unchanged(self, legacy_database, before)


if __name__ == "__main__":
    unittest.main()
