"""Pruebas temporales de perfiles de sede y mantenimiento."""

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _file_assertions import assert_optional_file_unchanged, snapshot_optional_file
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import MigrationError, apply_migrations
from backend.fitpath.seeds import seed_initial_roles


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPOSITORY_ROOT / "backend" / "fitpath" / "migrations"
MIGRATION_VERSIONS = (1, 2, 3, 4, 5, 6, 7, 8, 9)


class MaintenanceSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "maintenance.sqlite3"
        self.connection = connect_database(self.database_path)
        self.addCleanup(self.connection.close)
        self.assertEqual(
            apply_migrations(self.connection, MIGRATIONS_DIR),
            MIGRATION_VERSIONS,
        )
        seed_initial_roles(self.connection)

        self.site_one = self.create_site("Centro")
        self.site_two = self.create_site("Norte")
        self.technician_user_one = self.create_user(
            "tecnico.uno", "Técnico de mantenimiento"
        )
        self.technician_user_two = self.create_user(
            "tecnico.dos", "Técnico de mantenimiento"
        )
        self.manager_user = self.create_user("jefe.sede", "Jefe de sede")
        self.technician_one = self.connection.execute(
            """
            INSERT INTO tecnicos_mantenimiento (usuario_id, sede_id)
            VALUES (?, ?)
            """,
            (self.technician_user_one, self.site_one),
        ).lastrowid
        self.technician_two = self.connection.execute(
            """
            INSERT INTO tecnicos_mantenimiento (usuario_id, sede_id)
            VALUES (?, ?)
            """,
            (self.technician_user_two, self.site_two),
        ).lastrowid
        self.manager_id = self.connection.execute(
            "INSERT INTO jefes_sede (usuario_id, sede_id) VALUES (?, ?)",
            (self.manager_user, self.site_one),
        ).lastrowid
        self.machine_one = self.create_machine(self.site_one)
        self.machine_two = self.create_machine(self.site_two)
        self.ticket_one = self.create_ticket(self.machine_one, self.technician_one)
        self.ticket_two = self.create_ticket(self.machine_two, self.technician_two)
        self.connection.commit()

        legacy_database = REPOSITORY_ROOT / "gimnasio.db"
        self.legacy_metadata = snapshot_optional_file(legacy_database)

    def create_site(self, name):
        return self.connection.execute(
            """
            INSERT INTO sedes (nombre, direccion, zona_horaria)
            VALUES (?, ?, ?)
            """,
            (name, "Dirección de prueba", "America/Argentina/Buenos_Aires"),
        ).lastrowid

    def create_user(self, username, role_name):
        role_id = self.connection.execute(
            "SELECT id_rol FROM roles WHERE nombre = ?",
            (role_name,),
        ).fetchone()[0]
        return self.connection.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Persona",
                "Prueba",
                username,
                username + "@example.test",
                role_id,
            ),
        ).lastrowid

    def create_machine(self, site_id, state="operativa", kind="Cinta"):
        return self.connection.execute(
            "INSERT INTO maquinas (sede_id, tipo, estado) VALUES (?, ?, ?)",
            (site_id, kind, state),
        ).lastrowid

    def create_ticket(
        self,
        machine_id,
        technician_id,
        state="abierto",
        timestamp="2026-11-09T12:00:00Z",
    ):
        return self.connection.execute(
            """
            INSERT INTO tickets_mantenimiento
                (maquina_id, tecnico_id, fecha_generacion_utc, descripcion, estado)
            VALUES (?, ?, ?, ?, ?)
            """,
            (machine_id, technician_id, timestamp, "Revisión de prueba", state),
        ).lastrowid

    def create_history(
        self,
        machine_id,
        ticket_id,
        technician_id,
        previous="operativa",
        new="en_reparacion",
        timestamp="2026-11-09T12:30:00Z",
    ):
        return self.connection.execute(
            """
            INSERT INTO historial_mantenimiento
                (maquina_id, ticket_id, tecnico_id, fecha_utc,
                 estado_anterior, estado_nuevo, descripcion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                machine_id,
                ticket_id,
                technician_id,
                timestamp,
                previous,
                new,
                "Cambio de estado de prueba",
            ),
        ).lastrowid

    def test_migration_creates_profiles_and_maintenance_tables(self):
        expected = {
            "tecnicos_mantenimiento",
            "jefes_sede",
            "maquinas",
            "tickets_mantenimiento",
            "historial_mantenimiento",
        }
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ?",
                ("table",),
            )
        }
        self.assertTrue(expected.issubset(tables))
        self.assertEqual(self.connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(self.connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(
            self.connection.execute(
                "SELECT name FROM schema_migrations WHERE version = ?",
                (7,),
            ).fetchone()[0],
            "0007_mantenimiento_perfiles.sql",
        )

    def test_technician_and_site_manager_profiles_require_unique_users_and_sites(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO tecnicos_mantenimiento (usuario_id, sede_id) VALUES (?, ?)",
                (self.technician_user_one, self.site_two),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO jefes_sede (usuario_id, sede_id) VALUES (?, ?)",
                (self.manager_user, self.site_two),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO tecnicos_mantenimiento (usuario_id, sede_id) VALUES (?, ?)",
                (999999, self.site_one),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO jefes_sede (usuario_id, sede_id) VALUES (?, ?)",
                (999999, self.site_one),
            )
        self.assertIsNotNone(self.manager_id)

    def test_machine_requires_site_type_and_approved_state(self):
        for site_id, kind, state in (
            (999999, "Cinta", "operativa"),
            (self.site_one, " ", "operativa"),
            (self.site_one, "Cinta", "inactiva"),
        ):
            with self.subTest(site=site_id, kind=kind, state=state):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.create_machine(site_id, state, kind)

    def test_ticket_requires_machine_technician_same_site_and_valid_fields(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_ticket(self.machine_one, self.technician_two)
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_ticket(999999, self.technician_one)
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_ticket(self.machine_one, self.technician_one, state="pendiente")
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_ticket(
                self.machine_one,
                self.technician_one,
                timestamp="2026-02-30T12:00:00Z",
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE tickets_mantenimiento SET tecnico_id = ? WHERE id_ticket = ?",
                (self.technician_two, self.ticket_one),
            )

    def test_history_requires_matching_machine_ticket_site_and_valid_states(self):
        first = self.create_history(
            self.machine_one,
            self.ticket_one,
            self.technician_one,
        )
        second = self.create_history(
            self.machine_one,
            self.ticket_one,
            self.technician_one,
            previous="en_reparacion",
            new="operativa",
            timestamp="2026-11-09T13:00:00Z",
        )
        self.assertNotEqual(first, second)
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM historial_mantenimiento WHERE maquina_id = ?",
                (self.machine_one,),
            ).fetchone()[0],
            2,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_history(self.machine_one, self.ticket_one, self.technician_two)
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_history(self.machine_two, self.ticket_one, self.technician_two)
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_history(
                self.machine_one,
                self.ticket_one,
                self.technician_one,
                previous="mantenimiento",
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_history(
                self.machine_one,
                self.ticket_one,
                self.technician_one,
                timestamp="2026-02-30T12:00:00Z",
            )

    def test_site_changes_cannot_make_existing_history_inconsistent(self):
        self.create_history(self.machine_one, self.ticket_one, self.technician_one)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE maquinas SET sede_id = ? WHERE id_maquina = ?",
                (self.site_two, self.machine_one),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE tecnicos_mantenimiento SET sede_id = ? WHERE id_tecnico = ?",
                (self.site_two, self.technician_one),
            )

    def test_historical_records_restrict_deletion_of_linked_data(self):
        history_id = self.create_history(
            self.machine_one,
            self.ticket_one,
            self.technician_one,
        )
        self.assertIsNotNone(history_id)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "DELETE FROM tickets_mantenimiento WHERE id_ticket = ?",
                (self.ticket_one,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "DELETE FROM maquinas WHERE id_maquina = ?",
                (self.machine_one,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "DELETE FROM tecnicos_mantenimiento WHERE id_tecnico = ?",
                (self.technician_one,),
            )

    def test_migrations_are_idempotent_and_checksum_protected(self):
        self.assertEqual(apply_migrations(self.connection, MIGRATIONS_DIR), ())
        self.assertEqual(
            self.connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0],
            9,
        )
        copied_migrations = self.root / "checksum-migrations"
        copied_migrations.mkdir()
        for migration in MIGRATIONS_DIR.glob("*.sql"):
            shutil.copyfile(migration, copied_migrations / migration.name)
        connection = connect_database(self.root / "checksum.sqlite3")
        self.addCleanup(connection.close)
        apply_migrations(connection, copied_migrations)
        with (copied_migrations / "0007_mantenimiento_perfiles.sql").open(
            "a", encoding="utf-8"
        ) as migration_file:
            migration_file.write("\n-- alteración posterior\n")
        with self.assertRaises(MigrationError):
            apply_migrations(connection, copied_migrations)

    def test_failed_migration_rolls_back_all_version_seven_objects(self):
        broken_migrations = self.root / "broken-migrations"
        broken_migrations.mkdir()
        for migration in MIGRATIONS_DIR.glob("*.sql"):
            shutil.copyfile(migration, broken_migrations / migration.name)
        version_seven = broken_migrations / "0007_mantenimiento_perfiles.sql"
        with version_seven.open("a", encoding="utf-8") as migration_file:
            migration_file.write(
                "\nCREATE TABLE rollback_probe (id INTEGER PRIMARY KEY);\n"
                "INVALID SQL;\n"
            )

        connection = connect_database(self.root / "rollback.sqlite3")
        self.addCleanup(connection.close)
        with self.assertRaises(MigrationError):
            apply_migrations(connection, broken_migrations)
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ?",
                ("table",),
            )
        }
        self.assertTrue({"pagos", "clases", "roles"}.issubset(tables))
        self.assertTrue(
            {
                "tecnicos_mantenimiento",
                "jefes_sede",
                "maquinas",
                "tickets_mantenimiento",
                "historial_mantenimiento",
                "rollback_probe",
            }.isdisjoint(tables)
        )
        self.assertEqual(
            tuple(
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ),
            (1, 2, 3, 4, 5, 6),
        )
        self.assertFalse(connection.in_transaction)

    def test_legacy_database_metadata_remains_unchanged(self):
        legacy_database = REPOSITORY_ROOT / "gimnasio.db"
        assert_optional_file_unchanged(self, legacy_database, self.legacy_metadata)


if __name__ == "__main__":
    unittest.main()
