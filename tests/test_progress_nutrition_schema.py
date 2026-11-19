"""Pruebas temporales de progreso físico y planes de alimentación."""

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


class ProgressNutritionSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.connection = connect_database(self.root / "progress-nutrition.sqlite3")
        self.addCleanup(self.connection.close)
        self.assertEqual(
            apply_migrations(self.connection, MIGRATIONS_DIR),
            tuple(range(1, 15)),
        )
        seed_initial_roles(self.connection)
        client_role = self.connection.execute(
            "SELECT id_rol FROM roles WHERE nombre = ?", ("Cliente",)
        ).fetchone()[0]
        user_id = self.connection.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("Lucía", "Prueba", "lucia.cliente", "lucia@example.com", client_role),
        ).lastrowid
        self.client_id = self.connection.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (user_id,)
        ).lastrowid
        objective_type = self.connection.execute(
            "INSERT INTO tipos_objetivo (nombre) VALUES (?)", ("Bienestar",)
        ).lastrowid
        self.objective_id = self.connection.execute(
            """
            INSERT INTO objetivos (tipo_objetivo_id, nombre)
            VALUES (?, ?)
            """,
            (objective_type, "Mejorar hábitos"),
        ).lastrowid
        self.connection.commit()

        self.legacy_database = REPOSITORY_ROOT / "gimnasio.db"
        self.legacy_metadata = snapshot_optional_file(self.legacy_database)

    def create_progress(
        self,
        client_id=None,
        timestamp="2026-11-08T12:00:00Z",
        weight=70.5,
        body_fat=20.0,
        performance="Entrenamiento registrado",
        observations="Medición de prueba",
    ):
        return self.connection.execute(
            """
            INSERT INTO progresos
                (
                    cliente_id, fecha_utc, peso_kg,
                    porcentaje_grasa, rendimiento_ejercicios, observaciones
                )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                client_id if client_id is not None else self.client_id,
                timestamp,
                weight,
                body_fat,
                performance,
                observations,
            ),
        ).lastrowid

    def create_food_plan(
        self,
        client_id=None,
        objective_id=None,
        name="Plan de prueba",
        description="Descripción de prueba",
        instructions="Indicaciones de prueba",
        created="2026-11-08T12:00:00Z",
        updated="2026-11-08T12:00:00Z",
    ):
        return self.connection.execute(
            """
            INSERT INTO planes_alimentacion
                (
                    cliente_id, objetivo_id, nombre, descripcion, indicaciones,
                    fecha_creacion_utc, fecha_actualizacion_utc
                )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id if client_id is not None else self.client_id,
                objective_id if objective_id is not None else self.objective_id,
                name,
                description,
                instructions,
                created,
                updated,
            ),
        ).lastrowid

    def test_migration_creates_tables_with_valid_foreign_keys(self):
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ?", ("table",)
            )
        }
        self.assertTrue({"progresos", "planes_alimentacion"}.issubset(tables))
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_keys").fetchone()[0], 1
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(), []
        )

    def test_progress_belongs_to_client_and_preserves_multiple_measurements(self):
        first = self.create_progress(timestamp="2026-11-01T10:00:00Z")
        second = self.create_progress(
            timestamp="2026-11-08T10:00:00Z", weight=69.8, body_fat=19.5
        )
        self.assertNotEqual(first, second)
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM progresos WHERE cliente_id = ?",
                (self.client_id,),
            ).fetchone()[0],
            2,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_progress(client_id=999999)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "DELETE FROM clientes WHERE id_cliente = ?", (self.client_id,)
            )

    def test_invalid_measurements_dates_and_non_numeric_values_are_rejected(self):
        invalid = (
            {"weight": 0},
            {"weight": -1},
            {"weight": "no numérico"},
            {"body_fat": -0.01},
            {"body_fat": 100.01},
            {"body_fat": "no numérico"},
            {"timestamp": "2026-02-30T12:00:00Z"},
        )
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.create_progress(**values)

    def test_food_plans_keep_client_objective_and_date_references(self):
        first = self.create_food_plan()
        second = self.create_food_plan(
            name="Plan posterior",
            created="2026-11-09T12:00:00Z",
            updated="2026-11-10T12:00:00Z",
        )
        self.assertNotEqual(first, second)
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_food_plan(client_id=999999)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO planes_alimentacion
                    (cliente_id, objetivo_id, nombre, fecha_creacion_utc,
                     fecha_actualizacion_utc)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self.client_id,
                    999999,
                    "Objetivo inexistente",
                    "2026-11-08T12:00:00Z",
                    "2026-11-08T12:00:00Z",
                ),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_food_plan(name="   ")
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_food_plan(
                created="2026-11-09T12:00:00Z",
                updated="2026-11-08T12:00:00Z",
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_food_plan(
                created="invalid",
                updated="invalid",
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "DELETE FROM objetivos WHERE id_objetivo = ?",
                (self.objective_id,),
            )

    def test_plan_requires_objective_and_leaves_client_ownership_open(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO planes_alimentacion
                    (cliente_id, nombre, fecha_creacion_utc, fecha_actualizacion_utc)
                VALUES (?, ?, ?, ?)
                """,
                (
                    self.client_id,
                    "Sin objetivo",
                    "2026-11-08T12:00:00Z",
                    "2026-11-08T12:00:00Z",
                ),
            )
        # La pertenencia del objetivo al cliente queda pendiente y no se infiere aquí.

    def test_migrations_are_idempotent_and_record_all_versions(self):
        self.connection.commit()
        self.assertEqual(apply_migrations(self.connection, MIGRATIONS_DIR), ())
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM schema_migrations"
            ).fetchone()[0],
            14,
        )
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(), []
        )

    def test_failed_version_five_migration_rolls_back_partial_schema(self):
        broken_migrations = self.root / "broken-migrations"
        broken_migrations.mkdir()
        for migration in MIGRATIONS_DIR.glob("*.sql"):
            shutil.copyfile(migration, broken_migrations / migration.name)
        version_five = broken_migrations / "0005_progreso_alimentacion.sql"
        with version_five.open("a", encoding="utf-8") as migration_file:
            migration_file.write(
                "\nCREATE TABLE rollback_marker (id INTEGER PRIMARY KEY);\n"
                "INVALID SQL;\n"
            )

        connection = connect_database(self.root / "rollback.sqlite3")
        self.addCleanup(connection.close)
        with self.assertRaises(MigrationError):
            apply_migrations(connection, broken_migrations)

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ?", ("table",)
            )
        }
        self.assertNotIn("rollback_marker", tables)
        self.assertTrue({"progresos", "planes_alimentacion"}.isdisjoint(tables))
        self.assertEqual(
            tuple(
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ),
            (1, 2, 3, 4),
        )
        self.assertFalse(connection.in_transaction)

    def test_legacy_database_metadata_remains_unchanged(self):
        assert_optional_file_unchanged(
            self, self.legacy_database, self.legacy_metadata
        )


if __name__ == "__main__":
    unittest.main()
