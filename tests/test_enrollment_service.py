"""Pruebas temporales del perfil Cliente, inscripciones y asistencias."""

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from _file_assertions import assert_optional_file_unchanged, snapshot_optional_file
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.seeds import seed_initial_roles
from backend.fitpath.services.enrollments import (
    ClassFullError,
    ClassNotFoundError,
    ClassUnavailableError,
    ClientNotFoundError,
    DuplicateActiveEnrollmentError,
    EnrollmentConfigurationError,
    create_enrollment,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPOSITORY_ROOT / "backend" / "fitpath" / "migrations"


class EnrollmentSchemaAndServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "fitpath.sqlite3"
        self.connection = connect_database(self.database_path, timeout=10.0)
        self.addCleanup(self.connection.close)

        self.assertEqual(
            apply_migrations(self.connection, MIGRATIONS_DIR),
            (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
        )
        seed_initial_roles(self.connection)

        self.client_role_id = self.role_id("Cliente")
        self.trainer_role_id = self.role_id("Entrenador")
        self.client_id = self.create_client(
            "Clara",
            "clara.cliente",
            "clara@example.com",
        )
        self.other_client_id = self.create_client(
            "Mateo",
            "mateo.cliente",
            "mateo@example.com",
        )
        trainer_user_id = self.create_user(
            "Eva",
            "eva.entrenadora",
            "eva@example.com",
            self.trainer_role_id,
        )
        self.trainer_id = self.connection.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, ?)",
            (trainer_user_id, "Fuerza"),
        ).lastrowid
        self.site_id = self.connection.execute(
            """
            INSERT INTO sedes (nombre, direccion, zona_horaria)
            VALUES (?, ?, ?)
            """,
            ("Centro", "Calle 123", "America/Argentina/Buenos_Aires"),
        ).lastrowid
        self.activity_id = self.connection.execute(
            "INSERT INTO actividades (nombre) VALUES (?)",
            ("Fuerza",),
        ).lastrowid
        self.connection.execute(
            """
            INSERT INTO entrenador_sede (entrenador_id, sede_id, activo)
            VALUES (?, ?, ?)
            """,
            (self.trainer_id, self.site_id, 1),
        )
        self.connection.execute(
            """
            INSERT INTO actividad_sede (actividad_id, sede_id, habilitada)
            VALUES (?, ?, ?)
            """,
            (self.activity_id, self.site_id, 1),
        )
        self.class_id = self.create_class()
        self.connection.commit()

        self.legacy_database = REPOSITORY_ROOT / "gimnasio.db"
        self.legacy_metadata = snapshot_optional_file(self.legacy_database)

    def role_id(self, name):
        row = self.connection.execute(
            "SELECT id_rol FROM roles WHERE nombre = ?",
            (name,),
        ).fetchone()
        return row[0]

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
        user_id = self.create_user(
            name,
            username,
            email,
            self.client_role_id,
        )
        return self.connection.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)",
            (user_id,),
        ).lastrowid

    def create_class(
        self,
        capacity=4,
        state="programada",
        start="2099-08-10T12:00:00Z",
        end="2099-08-10T13:00:00Z",
    ):
        return self.connection.execute(
            """
            INSERT INTO clases
                (
                    actividad_id, sede_id, entrenador_id,
                    inicio_utc, fin_utc, cupo_maximo, estado
                )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.activity_id,
                self.site_id,
                self.trainer_id,
                start,
                end,
                capacity,
                state,
            ),
        ).lastrowid

    def test_migration_creates_client_enrollment_and_attendance_tables(self):
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ?",
                ("table",),
            )
        }
        self.assertEqual(
            tables,
            {
                "schema_migrations",
                "roles",
                "permisos",
                "rol_permiso",
                "usuarios",
                "sedes",
                "entrenadores",
                "entrenador_sede",
                "actividades",
                "actividad_sede",
                "disponibilidad_entrenador",
                "clases",
                "clientes",
                "inscripciones",
                "asistencias",
                "tipos_objetivo",
                "objetivos",
                "cliente_objetivo",
                "rutinas",
                "ejercicios",
                "rutina_ejercicio",
                "progresos",
                "planes_alimentacion",
                "monedas",
                "membresias",
                "beneficios",
                "membresia_beneficio",
                "cliente_membresia",
                "deudas",
                "pagos",
                "tecnicos_mantenimiento",
                "jefes_sede",
                "maquinas",
                "tickets_mantenimiento",
                "historial_mantenimiento",
                "remuneraciones",
                "identidades_google",
                "solicitudes_vinculo_google",
                "intentos_pago",
                "eventos_webhook_pago",
            },
        )
        versions = tuple(
            (row["version"], row["name"])
            for row in self.connection.execute(
                "SELECT version, name FROM schema_migrations ORDER BY version"
            )
        )
        self.assertEqual(
            versions,
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
                (10, "0010_cliente_imagen_perfil.sql"),
                (11, "0011_mercado_pago_intentos.sql"),
            ),
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_keys").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(),
            [],
        )
        indexes = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ?",
                ("index",),
            )
        }
        self.assertTrue(
            {
                "uq_inscripciones_activas_cliente_clase",
                "idx_inscripciones_cliente_fecha",
                "idx_inscripciones_clase_estado",
            }.issubset(indexes)
        )

        enrollment_foreign_keys = {
            row["table"]
            for row in self.connection.execute(
                "PRAGMA foreign_key_list('inscripciones')"
            )
        }
        self.assertEqual(enrollment_foreign_keys, {"clientes", "clases"})
        attendance_foreign_keys = {
            row["table"]
            for row in self.connection.execute(
                "PRAGMA foreign_key_list('asistencias')"
            )
        }
        self.assertEqual(attendance_foreign_keys, {"inscripciones"})

    def test_enrollment_timestamp_and_state_constraints_are_enforced(self):
        invalid_rows = (
            ("2026-11-08 12:00:00", "activa"),
            ("2026-02-30T12:00:00Z", "activa"),
            ("2026-11-08T12:00:00Z", "pendiente"),
        )
        for timestamp, state in invalid_rows:
            with self.subTest(timestamp=timestamp, state=state):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
                        """
                        INSERT INTO inscripciones
                            (cliente_id, clase_id, fecha_utc, estado)
                        VALUES (?, ?, ?, ?)
                        """,
                        (self.client_id, self.class_id, timestamp, state),
                    )
                self.connection.rollback()

        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(
            self.connection.execute("SELECT count(*) FROM inscripciones").fetchone()[0],
            0,
        )

    def test_client_profile_requires_existing_unique_user(self):
        user_id = self.connection.execute(
            "SELECT usuario_id FROM clientes WHERE id_cliente = ?",
            (self.client_id,),
        ).fetchone()[0]
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO clientes (usuario_id) VALUES (?)",
                (user_id,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO clientes (usuario_id) VALUES (?)",
                (999999,),
            )
        self.connection.rollback()

    def test_valid_enrollment_uses_one_active_row_and_calculates_capacity(self):
        enrollment_id = create_enrollment(
            self.connection,
            self.client_id,
            self.class_id,
        )
        self.assertGreater(enrollment_id, 0)
        self.assertFalse(self.connection.in_transaction)
        row = self.connection.execute(
            """
            SELECT cliente_id, clase_id, fecha_utc, estado
            FROM inscripciones
            WHERE id_inscripcion = ?
            """,
            (enrollment_id,),
        ).fetchone()
        self.assertEqual(row["cliente_id"], self.client_id)
        self.assertEqual(row["clase_id"], self.class_id)
        self.assertRegex(
            row["fecha_utc"],
            r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$",
        )
        self.assertEqual(row["estado"], "activa")
        active_count = self.connection.execute(
            """
            SELECT count(*)
            FROM inscripciones
            WHERE clase_id = ? AND estado = ?
            """,
            (self.class_id, "activa"),
        ).fetchone()[0]
        capacity = self.connection.execute(
            "SELECT cupo_maximo FROM clases WHERE id_clase = ?",
            (self.class_id,),
        ).fetchone()[0]
        self.assertEqual(capacity - active_count, 3)

    def test_active_enrollment_duplicate_is_rejected_by_service_and_index(self):
        create_enrollment(self.connection, self.client_id, self.class_id)
        with self.assertRaises(DuplicateActiveEnrollmentError):
            create_enrollment(self.connection, self.client_id, self.class_id)
        self.assertFalse(self.connection.in_transaction)

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO inscripciones (cliente_id, clase_id, fecha_utc, estado)
                VALUES (?, ?, ?, ?)
                """,
                (
                    self.client_id,
                    self.class_id,
                    "2026-11-08T12:00:00Z",
                    "activa",
                ),
            )
        self.connection.rollback()
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM inscripciones WHERE estado = ?",
                ("activa",),
            ).fetchone()[0],
            1,
        )

    def test_full_class_is_rejected_and_failed_operation_rolls_back(self):
        full_class_id = self.create_class(capacity=1)
        self.connection.commit()
        create_enrollment(self.connection, self.client_id, full_class_id)

        with self.assertRaises(ClassFullError):
            create_enrollment(
                self.connection,
                self.other_client_id,
                full_class_id,
            )

        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(
            self.connection.execute(
                """
                SELECT count(*)
                FROM inscripciones
                WHERE clase_id = ? AND estado = ?
                """,
                (full_class_id, "activa"),
            ).fetchone()[0],
            1,
        )

    def test_class_and_client_must_exist(self):
        with self.assertRaises(ClientNotFoundError):
            create_enrollment(self.connection, 999999, self.class_id)
        self.assertFalse(self.connection.in_transaction)
        with self.assertRaises(ClassNotFoundError):
            create_enrollment(self.connection, self.client_id, 999999)
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM inscripciones"
            ).fetchone()[0],
            0,
        )

    def test_non_programmed_disabled_or_past_class_is_unavailable(self):
        canceled_class_id = self.create_class(capacity=2, state="cancelada")
        past_class_id = self.create_class(
            capacity=2,
            start="2000-08-10T12:00:00Z",
            end="2000-08-10T13:00:00Z",
        )
        self.connection.commit()

        with self.assertRaises(ClassUnavailableError):
            create_enrollment(self.connection, self.client_id, canceled_class_id)
        self.assertFalse(self.connection.in_transaction)
        with self.assertRaises(ClassUnavailableError):
            create_enrollment(self.connection, self.client_id, past_class_id)
        self.assertFalse(self.connection.in_transaction)

        self.connection.execute(
            "UPDATE actividad_sede SET habilitada = ? WHERE actividad_id = ? AND sede_id = ?",
            (0, self.activity_id, self.site_id),
        )
        self.connection.commit()
        with self.assertRaises(ClassUnavailableError):
            create_enrollment(self.connection, self.client_id, self.class_id)
        self.assertFalse(self.connection.in_transaction)

    def test_inactive_trainer_site_prevents_new_enrollment(self):
        self.connection.execute(
            """
            UPDATE entrenador_sede SET activo = ?
            WHERE entrenador_id = ? AND sede_id = ?
            """,
            (0, self.trainer_id, self.site_id),
        )
        self.connection.commit()
        with self.assertRaises(ClassUnavailableError):
            create_enrollment(self.connection, self.client_id, self.class_id)
        self.assertFalse(self.connection.in_transaction)

    def test_cancellation_history_is_kept_and_does_not_consume_capacity(self):
        old_id = create_enrollment(self.connection, self.client_id, self.class_id)
        self.connection.execute(
            "UPDATE inscripciones SET estado = ? WHERE id_inscripcion = ?",
            ("cancelada", old_id),
        )
        self.connection.commit()

        new_id = create_enrollment(self.connection, self.client_id, self.class_id)
        rows = self.connection.execute(
            """
            SELECT id_inscripcion, estado
            FROM inscripciones
            WHERE cliente_id = ? AND clase_id = ?
            ORDER BY id_inscripcion
            """,
            (self.client_id, self.class_id),
        ).fetchall()
        self.assertNotEqual(old_id, new_id)
        self.assertEqual(
            [(row["id_inscripcion"], row["estado"]) for row in rows],
            [(old_id, "cancelada"), (new_id, "activa")],
        )

    def test_attendance_is_unique_per_enrollment_and_references_existing_row(self):
        enrollment_id = create_enrollment(
            self.connection,
            self.client_id,
            self.class_id,
        )
        attendance = (
            enrollment_id,
            "2026-11-08T12:00:00Z",
            "presente",
        )
        self.connection.execute(
            """
            INSERT INTO asistencias (inscripcion_id, fecha_utc, estado)
            VALUES (?, ?, ?)
            """,
            attendance,
        )
        self.connection.commit()

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO asistencias (inscripcion_id, fecha_utc, estado)
                VALUES (?, ?, ?)
                """,
                attendance,
            )
        self.connection.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO asistencias (inscripcion_id, fecha_utc, estado)
                VALUES (?, ?, ?)
                """,
                (999999, "2026-11-08T12:00:00Z", "presente"),
            )
        self.connection.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO asistencias (inscripcion_id, fecha_utc, estado)
                VALUES (?, ?, ?)
                """,
                (enrollment_id, "2026-11-08T12:00:00Z", "pendiente"),
            )
        self.connection.rollback()
        self.assertEqual(
            self.connection.execute("SELECT count(*) FROM asistencias").fetchone()[0],
            1,
        )

    def test_restrictive_foreign_keys_preserve_enrollment_history(self):
        enrollment_id = create_enrollment(
            self.connection,
            self.client_id,
            self.class_id,
        )
        self.connection.execute(
            """
            INSERT INTO asistencias (inscripcion_id, fecha_utc, estado)
            VALUES (?, ?, ?)
            """,
            (enrollment_id, "2026-11-08T12:00:00Z", "ausente"),
        )
        self.connection.commit()

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "DELETE FROM inscripciones WHERE id_inscripcion = ?",
                (enrollment_id,),
            )
        self.connection.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "DELETE FROM clientes WHERE id_cliente = ?",
                (self.client_id,),
            )
        self.connection.rollback()
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM asistencias WHERE inscripcion_id = ?",
                (enrollment_id,),
            ).fetchone()[0],
            1,
        )

    def test_concurrent_enrollments_do_not_exceed_class_capacity(self):
        capacity_one_class = self.create_class(capacity=1)
        self.connection.commit()
        barrier = Barrier(2)

        def attempt(client_id):
            connection = connect_database(self.database_path, timeout=10.0)
            try:
                barrier.wait(timeout=10)
                enrollment_id = create_enrollment(
                    connection,
                    client_id,
                    capacity_one_class,
                )
                return ("created", enrollment_id)
            except ClassFullError:
                return ("full", None)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    attempt,
                    (self.client_id, self.other_client_id),
                )
            )

        self.assertCountEqual([result[0] for result in results], ["created", "full"])
        self.assertEqual(
            self.connection.execute(
                """
                SELECT count(*)
                FROM inscripciones
                WHERE clase_id = ? AND estado = ?
                """,
                (capacity_one_class, "activa"),
            ).fetchone()[0],
            1,
        )

    def test_migrations_are_idempotent_and_foreign_keys_remain_valid(self):
        self.connection.commit()
        self.assertEqual(
            apply_migrations(self.connection, MIGRATIONS_DIR),
            (),
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM schema_migrations"
            ).fetchone()[0],
            11,
        )
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(),
            [],
        )

    def test_service_requires_foreign_keys_enabled_and_no_open_transaction(self):
        self.connection.execute("PRAGMA foreign_keys = OFF")
        with self.assertRaises(EnrollmentConfigurationError):
            create_enrollment(self.connection, self.client_id, self.class_id)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute(
            "UPDATE usuarios SET activo = activo WHERE id_usuario = ?",
            (
                self.connection.execute(
                    "SELECT usuario_id FROM clientes WHERE id_cliente = ?",
                    (self.client_id,),
                ).fetchone()[0],
            ),
        )
        self.assertTrue(self.connection.in_transaction)
        with self.assertRaises(EnrollmentConfigurationError):
            create_enrollment(self.connection, self.client_id, self.class_id)
        self.assertTrue(self.connection.in_transaction)
        self.connection.rollback()

    def test_legacy_database_metadata_is_unchanged(self):
        create_enrollment(self.connection, self.client_id, self.class_id)
        assert_optional_file_unchanged(
            self, self.legacy_database, self.legacy_metadata
        )


if __name__ == "__main__":
    unittest.main()
