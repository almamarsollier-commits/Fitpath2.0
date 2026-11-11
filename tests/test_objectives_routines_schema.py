"""Pruebas temporales de objetivos, rutinas y ejercicios."""

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.fitpath.database import connect_database
from backend.fitpath.migrations import MigrationError, apply_migrations
from backend.fitpath.seeds import seed_initial_roles


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPOSITORY_ROOT / "backend" / "fitpath" / "migrations"


class ObjectiveRoutineSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "objectives-routines.sqlite3"
        self.connection = connect_database(self.database_path)
        self.addCleanup(self.connection.close)
        self.assertEqual(
            apply_migrations(self.connection, MIGRATIONS_DIR),
            (1, 2, 3, 4, 5, 6, 7),
        )
        seed_initial_roles(self.connection)
        self.client_role_id = self.role_id("Cliente")
        self.trainer_role_id = self.role_id("Entrenador")
        self.client_id = self.create_client("Ana", "ana.cliente", "ana@example.com")
        self.other_client_id = self.create_client(
            "Bruno", "bruno.cliente", "bruno@example.com"
        )
        trainer_user_id = self.create_user(
            "Eva", "eva.entrenadora", "eva@example.com", self.trainer_role_id
        )
        self.trainer_id = self.connection.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, ?)",
            (trainer_user_id, "Fuerza"),
        ).lastrowid
        self.connection.commit()
        self.legacy_database = REPOSITORY_ROOT / "gimnasio.db"
        legacy_stat = self.legacy_database.stat()
        self.legacy_metadata = (legacy_stat.st_size, legacy_stat.st_mtime_ns)

    def role_id(self, name):
        return self.connection.execute(
            "SELECT id_rol FROM roles WHERE nombre = ?", (name,)
        ).fetchone()[0]

    def create_user(self, name, username, email, role_id):
        return self.connection.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, "Prueba", username, email, role_id),
        ).lastrowid

    def create_client(self, name, username, email):
        user_id = self.create_user(name, username, email, self.client_role_id)
        return self.connection.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (user_id,)
        ).lastrowid

    def create_objective_type(self, name="Fuerza"):
        return self.connection.execute(
            "INSERT INTO tipos_objetivo (nombre) VALUES (?)", (name,)
        ).lastrowid

    def create_objective(self, type_id, name="Aumentar fuerza"):
        return self.connection.execute(
            """
            INSERT INTO objetivos (tipo_objetivo_id, nombre, descripcion)
            VALUES (?, ?, ?)
            """,
            (type_id, name, "Descripción de prueba"),
        ).lastrowid

    def create_routine(self, client_id=None, trainer_id=None, objective_id=None):
        return self.connection.execute(
            """
            INSERT INTO rutinas
                (
                    nombre, descripcion, fecha_creacion_utc,
                    entrenador_id, cliente_id, objetivo_id,
                    observaciones_entrenador
                )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Rutina de prueba",
                "Descripción de prueba",
                "2026-11-08T12:00:00Z",
                trainer_id if trainer_id is not None else self.trainer_id,
                client_id if client_id is not None else self.client_id,
                objective_id,
                "Observación de prueba",
            ),
        ).lastrowid

    def create_exercise(self, name="Sentadilla"):
        return self.connection.execute(
            """
            INSERT INTO ejercicios (nombre, grupo_muscular, descripcion)
            VALUES (?, ?, ?)
            """,
            (name, "Piernas", "Ejercicio de prueba"),
        ).lastrowid

    def add_routine_exercise(
        self,
        routine_id,
        exercise_id,
        order=1,
        sets=3,
        repetitions=10,
        weight_grams=None,
        rest_seconds=60,
    ):
        return self.connection.execute(
            """
            INSERT INTO rutina_ejercicio
                (
                    rutina_id, ejercicio_id, orden, series,
                    repeticiones, peso_gramos, descanso_segundos
                )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                routine_id,
                exercise_id,
                order,
                sets,
                repetitions,
                weight_grams,
                rest_seconds,
            ),
        ).lastrowid

    def test_migration_creates_all_tables_and_foreign_keys_are_valid(self):
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ?", ("table",)
            )
        }
        self.assertTrue(
            {
                "tipos_objetivo",
                "objetivos",
                "cliente_objetivo",
                "rutinas",
                "ejercicios",
                "rutina_ejercicio",
            }.issubset(tables)
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_keys").fetchone()[0], 1
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(), []
        )

    def test_objectives_reference_types_and_avoid_same_type_duplicates(self):
        strength_type = self.create_objective_type()
        endurance_type = self.create_objective_type("Resistencia")
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_objective_type("Fuerza")
        objective_id = self.create_objective(strength_type)
        same_name_other_type = self.create_objective(endurance_type)

        self.assertNotEqual(objective_id, same_name_other_type)
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_objective(strength_type)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO objetivos (tipo_objetivo_id, nombre) VALUES (?, ?)",
                (999999, "Objetivo sin tipo"),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_objective_type("   ")

    def test_client_objectives_are_many_to_many_without_duplicate_pairs(self):
        objective_type = self.create_objective_type()
        first_objective = self.create_objective(objective_type, "Fuerza general")
        second_objective = self.create_objective(objective_type, "Resistencia")
        insert = """
            INSERT INTO cliente_objetivo (cliente_id, objetivo_id)
            VALUES (?, ?)
        """
        self.connection.execute(insert, (self.client_id, first_objective))
        self.connection.execute(insert, (self.client_id, second_objective))
        self.connection.execute(insert, (self.other_client_id, first_objective))
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(insert, (self.client_id, first_objective))
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(insert, (999999, first_objective))

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(insert, (self.client_id, 999999))

    def test_routines_require_existing_client_and_trainer_and_allow_optional_objective(self):
        objective_type = self.create_objective_type()
        objective_id = self.create_objective(objective_type)
        self.connection.execute(
            "INSERT INTO cliente_objetivo (cliente_id, objetivo_id) VALUES (?, ?)",
            (self.client_id, objective_id),
        )
        routine_without_objective = self.create_routine()
        routine_with_objective = self.create_routine(objective_id=objective_id)
        self.assertIsNotNone(routine_without_objective)
        self.assertEqual(
            self.connection.execute(
                "SELECT objetivo_id FROM rutinas WHERE id_rutina = ?",
                (routine_with_objective,),
            ).fetchone()[0],
            objective_id,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_routine(client_id=999999)
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_routine(trainer_id=999999)
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_routine(objective_id=999999)

    def test_routine_exercises_store_individual_parameters_and_allow_reuse(self):
        routine_one = self.create_routine()
        routine_two = self.create_routine(client_id=self.other_client_id)
        squat = self.create_exercise()
        pushup = self.create_exercise("Flexión de brazos")

        item_id = self.add_routine_exercise(
            routine_one, squat, order=1, sets=4, repetitions=8,
            weight_grams=25000, rest_seconds=90,
        )
        self.add_routine_exercise(routine_one, pushup, order=2)
        self.add_routine_exercise(routine_two, squat, order=1)

        row = self.connection.execute(
            """
            SELECT series, repeticiones, peso_gramos, descanso_segundos
            FROM rutina_ejercicio
            WHERE id_rutina_ejercicio = ?
            """,
            (item_id,),
        ).fetchone()
        self.assertEqual(tuple(row), (4, 8, 25000, 90))

    def test_required_names_and_routine_utc_timestamp_are_validated(self):
        type_id = self.create_objective_type()
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_objective(type_id, "   ")
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO rutinas
                    (nombre, fecha_creacion_utc, entrenador_id, cliente_id)
                VALUES (?, ?, ?, ?)
                """,
                ("   ", "2026-11-08T12:00:00Z", self.trainer_id, self.client_id),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO rutinas
                    (nombre, fecha_creacion_utc, entrenador_id, cliente_id)
                VALUES (?, ?, ?, ?)
                """,
                ("Rutina", "2026-02-30T12:00:00Z", self.trainer_id, self.client_id),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_exercise("   ")

    def test_restrictive_foreign_keys_preserve_referenced_history(self):
        type_id = self.create_objective_type()
        objective_id = self.create_objective(type_id)
        self.connection.execute(
            "INSERT INTO cliente_objetivo (cliente_id, objetivo_id) VALUES (?, ?)",
            (self.client_id, objective_id),
        )
        routine_id = self.create_routine(objective_id=objective_id)
        exercise_id = self.create_exercise()
        self.add_routine_exercise(routine_id, exercise_id)

        references = (
            ("DELETE FROM tipos_objetivo WHERE id_tipo_objetivo = ?", type_id),
            ("DELETE FROM objetivos WHERE id_objetivo = ?", objective_id),
            ("DELETE FROM clientes WHERE id_cliente = ?", self.client_id),
            ("DELETE FROM entrenadores WHERE id_entrenador = ?", self.trainer_id),
            ("DELETE FROM rutinas WHERE id_rutina = ?", routine_id),
            ("DELETE FROM ejercicios WHERE id_ejercicio = ?", exercise_id),
        )
        for statement, identifier in references:
            with self.subTest(statement=statement):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(statement, (identifier,))

    def test_invalid_routine_exercise_parameters_and_duplicate_order_are_rejected(self):
        routine_id = self.create_routine()
        exercise_id = self.create_exercise()
        invalid_parameters = (
            (0, 3, 8, None, 60),
            (1, 0, 8, None, 60),
            (1, 3, 0, None, 60),
            (1, 3, 8, -1, 60),
            (1, 3, 8, None, -1),
            (1, 3, 8, 1000.5, 60),
            (1.5, 3, 8, None, 60),
            (1, 3.5, 8, None, 60),
            (1, 3, 8, 1000, 1.5),
        )
        for parameters in invalid_parameters:
            with self.subTest(parameters=parameters):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.add_routine_exercise(
                        routine_id,
                        exercise_id,
                        order=parameters[0],
                        sets=parameters[1],
                        repetitions=parameters[2],
                        weight_grams=parameters[3],
                        rest_seconds=parameters[4],
                    )
        self.add_routine_exercise(routine_id, exercise_id, order=1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_routine_exercise(routine_id, exercise_id, order=1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_routine_exercise(routine_id, 999999, order=2)

    def test_migrations_are_idempotent_and_registry_has_seven_versions(self):
        self.connection.commit()
        self.assertEqual(apply_migrations(self.connection, MIGRATIONS_DIR), ())
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM schema_migrations"
            ).fetchone()[0],
            7,
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(), []
        )
        self.assertFalse(self.connection.in_transaction)

    def test_failed_version_four_migration_rolls_back_its_partial_schema(self):
        broken_migrations = self.root / "broken-migrations"
        broken_migrations.mkdir()
        for migration in MIGRATIONS_DIR.glob("*.sql"):
            destination = broken_migrations / migration.name
            shutil.copyfile(migration, destination)
        version_four = broken_migrations / "0004_objetivos_rutinas.sql"
        with version_four.open("a", encoding="utf-8") as migration_file:
            migration_file.write(
                "\nCREATE TABLE rollback_marker (id INTEGER PRIMARY KEY);\n"
                "INVALID SQL;\n"
            )

        database_path = self.root / "rollback.sqlite3"
        connection = connect_database(database_path)
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
        self.assertTrue(
            {
                "tipos_objetivo",
                "objetivos",
                "cliente_objetivo",
                "rutinas",
                "ejercicios",
                "rutina_ejercicio",
            }.isdisjoint(tables)
        )
        self.assertEqual(
            tuple(
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ),
            (1, 2, 3),
        )
        self.assertFalse(connection.in_transaction)

    def test_legacy_database_metadata_remains_unchanged(self):
        legacy_stat = self.legacy_database.stat()
        self.assertEqual(
            (legacy_stat.st_size, legacy_stat.st_mtime_ns),
            self.legacy_metadata,
        )


if __name__ == "__main__":
    unittest.main()
