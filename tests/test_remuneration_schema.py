"""Pruebas temporales de remuneraciones y su atribución histórica."""

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _file_assertions import assert_optional_file_unchanged, snapshot_optional_file
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import MigrationError, apply_migrations
from backend.fitpath.seeds import seed_initial_currencies, seed_initial_roles


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPOSITORY_ROOT / "backend" / "fitpath" / "migrations"
MIGRATION_VERSIONS = (1, 2, 3, 4, 5, 6, 7, 8, 9)


class RemunerationSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "remunerations.sqlite3"
        self.connection = connect_database(self.database_path)
        self.addCleanup(self.connection.close)
        self.assertEqual(
            apply_migrations(self.connection, MIGRATIONS_DIR),
            MIGRATION_VERSIONS,
        )
        seed_initial_roles(self.connection)
        seed_initial_currencies(self.connection)

        self.site_id = self.connection.execute(
            """
            INSERT INTO sedes (nombre, direccion, zona_horaria)
            VALUES (?, ?, ?)
            """,
            ("Centro", "Dirección de prueba", "America/Argentina/Buenos_Aires"),
        ).lastrowid
        self.activity_id = self.connection.execute(
            "INSERT INTO actividades (nombre) VALUES (?)",
            ("Fuerza",),
        ).lastrowid
        self.connection.execute(
            "INSERT INTO actividad_sede (actividad_id, sede_id) VALUES (?, ?)",
            (self.activity_id, self.site_id),
        )
        self.trainer_id = self.create_trainer("principal")
        self.class_id = self.create_class()
        self.connection.commit()

        legacy_database = REPOSITORY_ROOT / "gimnasio.db"
        self.legacy_metadata = snapshot_optional_file(legacy_database)

    def create_trainer(self, suffix):
        role_id = self.connection.execute(
            "SELECT id_rol FROM roles WHERE nombre = ?",
            ("Entrenador",),
        ).fetchone()[0]
        user_id = self.connection.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Entrenador",
                suffix,
                "entrenador." + suffix,
                "entrenador." + suffix + "@example.test",
                role_id,
            ),
        ).lastrowid
        trainer_id = self.connection.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, ?)",
            (user_id, "Fuerza"),
        ).lastrowid
        self.connection.execute(
            "INSERT INTO entrenador_sede (entrenador_id, sede_id) VALUES (?, ?)",
            (trainer_id, self.site_id),
        )
        return trainer_id

    def create_class(self, trainer_id=None):
        selected_trainer = trainer_id if trainer_id is not None else self.trainer_id
        sequence = self.connection.execute(
            "SELECT count(*) FROM clases"
        ).fetchone()[0]
        hour = 10 + sequence
        return self.connection.execute(
            """
            INSERT INTO clases
                (actividad_id, sede_id, entrenador_id, inicio_utc, fin_utc,
                 cupo_maximo, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.activity_id,
                self.site_id,
                selected_trainer,
                "2099-08-10T{:02d}:00:00Z".format(hour),
                "2099-08-10T{:02d}:00:00Z".format(hour + 1),
                10,
                "programada",
            ),
        ).lastrowid

    def create_remuneration(
        self,
        class_id=None,
        amount=12500,
        currency="ARS",
        state="pendiente",
        settled_at=None,
    ):
        return self.connection.execute(
            """
            INSERT INTO remuneraciones
                (clase_id, importe_unidades_menores, moneda,
                 estado_liquidacion, liquidada_utc)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                class_id if class_id is not None else self.class_id,
                amount,
                currency,
                state,
                settled_at,
            ),
        ).lastrowid

    def test_migration_and_optional_remuneration_have_valid_foreign_keys(self):
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_keys").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(),
            [],
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM remuneraciones WHERE clase_id = ?",
                (self.class_id,),
            ).fetchone()[0],
            0,
        )
        foreign_tables = {
            row["table"]
            for row in self.connection.execute(
                "PRAGMA foreign_key_list('remuneraciones')"
            )
        }
        self.assertEqual(foreign_tables, {"clases", "monedas"})

    def test_creates_a_valid_pending_remuneration(self):
        remuneration_id = self.create_remuneration()
        row = self.connection.execute(
            """
            SELECT clase_id, importe_unidades_menores, moneda,
                   estado_liquidacion, liquidada_utc
            FROM remuneraciones WHERE id_remuneracion = ?
            """,
            (remuneration_id,),
        ).fetchone()
        self.assertEqual(tuple(row), (self.class_id, 12500, "ARS", "pendiente", None))

    def test_class_can_have_at_most_one_remuneration(self):
        self.create_remuneration()
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_remuneration(state="anulada")
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM remuneraciones WHERE clase_id = ?",
                (self.class_id,),
            ).fetchone()[0],
            1,
        )

    def test_class_and_currency_foreign_keys_are_restrictive(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_remuneration(class_id=999999)
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_remuneration(currency="XXX")
        self.create_remuneration()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "DELETE FROM clases WHERE id_clase = ?",
                (self.class_id,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "DELETE FROM monedas WHERE codigo = ?",
                ("ARS",),
            )

    def test_amount_must_be_a_nonnegative_integer_in_minor_units(self):
        zero_id = self.create_remuneration(amount=0)
        self.assertEqual(
            self.connection.execute(
                "SELECT importe_unidades_menores FROM remuneraciones WHERE id_remuneracion = ?",
                (zero_id,),
            ).fetchone()[0],
            0,
        )
        for amount in (-1, 1.5):
            with self.subTest(amount=amount):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.create_remuneration(
                        class_id=self.create_class(),
                        amount=amount,
                    )

    def test_liquidation_status_and_timestamp_must_match(self):
        self.create_remuneration(state="liquidada", settled_at="2026-11-09T12:00:00Z")
        self.create_remuneration(
            class_id=self.create_class(),
            state="anulada",
        )
        invalid_rows = (
            ("pendiente", "2026-11-09T12:00:00Z"),
            ("liquidada", None),
            ("anulada", "2026-11-09T12:00:00Z"),
            ("otro", None),
            ("liquidada", "2026-02-30T12:00:00Z"),
        )
        for state, settled_at in invalid_rows:
            with self.subTest(state=state, settled_at=settled_at):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.create_remuneration(
                        class_id=self.create_class(),
                        state=state,
                        settled_at=settled_at,
                    )

    def test_trainer_reassignment_cannot_change_historical_recipient(self):
        remuneration_id = self.create_remuneration()
        other_trainer_id = self.create_trainer("secundario")
        unremunerated_class_id = self.create_class()
        self.connection.execute(
            "UPDATE clases SET entrenador_id = ? WHERE id_clase = ?",
            (other_trainer_id, unremunerated_class_id),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE clases SET entrenador_id = ? WHERE id_clase = ?",
                (other_trainer_id, self.class_id),
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT entrenador_id FROM clases WHERE id_clase = ?",
                (self.class_id,),
            ).fetchone()[0],
            self.trainer_id,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE remuneraciones SET clase_id = ? WHERE id_remuneracion = ?",
                (unremunerated_class_id, remuneration_id),
            )

    def test_remuneration_history_cannot_be_deleted(self):
        remuneration_id = self.create_remuneration()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "DELETE FROM remuneraciones WHERE id_remuneracion = ?",
                (remuneration_id,),
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM remuneraciones WHERE id_remuneracion = ?",
                (remuneration_id,),
            ).fetchone()[0],
            1,
        )

    def test_migrations_are_idempotent_and_checksum_protected(self):
        self.assertEqual(apply_migrations(self.connection, MIGRATIONS_DIR), ())
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM schema_migrations"
            ).fetchone()[0],
            9,
        )
        copied_migrations = self.root / "checksum-migrations"
        copied_migrations.mkdir()
        for migration in MIGRATIONS_DIR.glob("*.sql"):
            shutil.copyfile(migration, copied_migrations / migration.name)
        connection = connect_database(self.root / "checksum.sqlite3")
        self.addCleanup(connection.close)
        apply_migrations(connection, copied_migrations)
        with (copied_migrations / "0008_remuneraciones.sql").open(
            "a", encoding="utf-8"
        ) as migration_file:
            migration_file.write("\n-- alteración posterior\n")
        with self.assertRaises(MigrationError):
            apply_migrations(connection, copied_migrations)

    def test_failed_migration_rolls_back_all_version_eight_objects(self):
        broken_migrations = self.root / "broken-migrations"
        broken_migrations.mkdir()
        for migration in MIGRATIONS_DIR.glob("*.sql"):
            shutil.copyfile(migration, broken_migrations / migration.name)
        with (broken_migrations / "0008_remuneraciones.sql").open(
            "a", encoding="utf-8"
        ) as migration_file:
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
        self.assertTrue({"pagos", "clases", "maquinas"}.issubset(tables))
        self.assertTrue({"remuneraciones", "rollback_probe"}.isdisjoint(tables))
        self.assertEqual(
            tuple(
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ),
            (1, 2, 3, 4, 5, 6, 7),
        )
        self.assertFalse(connection.in_transaction)

    def test_legacy_database_metadata_remains_unchanged(self):
        legacy_database = REPOSITORY_ROOT / "gimnasio.db"
        assert_optional_file_unchanged(self, legacy_database, self.legacy_metadata)


if __name__ == "__main__":
    unittest.main()
