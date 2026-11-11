"""Pruebas de actividades, entrenadores, disponibilidad y clases."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.fitpath.database import connect_database
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.seeds import seed_initial_roles


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPOSITORY_ROOT / "backend" / "fitpath" / "migrations"


class ActivityClassSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.connection = connect_database(self.root / "activities.sqlite3")
        self.addCleanup(self.connection.close)

        self.assertEqual(apply_migrations(self.connection, MIGRATIONS_DIR), (1, 2, 3, 4, 5, 6))
        seed_initial_roles(self.connection)

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
            ("Eva", "Sosa", "eva.entrenadora", "eva@example.com", role_id),
        ).lastrowid
        self.user_id = user_id
        self.trainer_id = self.connection.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, ?)",
            (user_id, "Fuerza"),
        ).lastrowid

        self.site_one = self.insert_site("Centro")
        self.site_two = self.insert_site("Norte")
        self.site_unlinked = self.insert_site("Sur")
        self.activity_one = self.insert_activity("Yoga")
        self.activity_two = self.insert_activity("Pilates")

        self.insert_trainer_site(self.trainer_id, self.site_one, active=1)

        self.insert_activity_site(self.activity_one, self.site_one, enabled=1)
        self.insert_activity_site(self.activity_one, self.site_two, enabled=0)
        self.insert_activity_site(self.activity_two, self.site_two, enabled=1)

    def insert_site(self, name):
        return self.connection.execute(
            """
            INSERT INTO sedes (nombre, direccion, zona_horaria)
            VALUES (?, ?, ?)
            """,
            (name, "Calle 123", "America/Argentina/Buenos_Aires"),
        ).lastrowid

    def insert_activity(self, name):
        return self.connection.execute(
            "INSERT INTO actividades (nombre) VALUES (?)",
            (name,),
        ).lastrowid

    def insert_trainer(self, username, email):
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
            (username, "Prueba", username, email, role_id),
        ).lastrowid
        return self.connection.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, ?)",
            (user_id, "General"),
        ).lastrowid

    def insert_trainer_site(self, trainer_id, site_id, active=1):
        return self.connection.execute(
            """
            INSERT INTO entrenador_sede (entrenador_id, sede_id, activo)
            VALUES (?, ?, ?)
            """,
            (trainer_id, site_id, active),
        )

    def insert_activity_site(self, activity_id, site_id, enabled=1):
        return self.connection.execute(
            """
            INSERT INTO actividad_sede (actividad_id, sede_id, habilitada)
            VALUES (?, ?, ?)
            """,
            (activity_id, site_id, enabled),
        )

    def insert_class(
        self,
        activity_id=None,
        site_id=None,
        trainer_id=None,
        start="2026-08-10T12:00:00Z",
        end="2026-08-10T13:00:00Z",
        capacity=12,
        state="programada",
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
                activity_id if activity_id is not None else self.activity_one,
                site_id if site_id is not None else self.site_one,
                trainer_id if trainer_id is not None else self.trainer_id,
                start,
                end,
                capacity,
                state,
            ),
        ).lastrowid

    def test_migrations_create_activity_and_enrollment_tables(self):
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
                "clases",
                "disponibilidad_entrenador",
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
            },
        )
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
            ),
        )
        self.assertTrue({"clientes", "inscripciones", "asistencias"}.issubset(tables))

    def test_trainer_profile_and_class_constraints_are_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, ?)",
                (self.user_id, "Otra especialidad"),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, ?)",
                (99999, "General"),
            )
        role_id = self.connection.execute(
            "SELECT id_rol FROM roles WHERE nombre = ?",
            ("Entrenador",),
        ).fetchone()[0]
        extra_user_id = self.connection.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("Vacio", "Prueba", "vacio", "vacio@example.com", role_id),
        ).lastrowid
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, ?)",
                (extra_user_id, " "),
            )
        class_fk_tables = {
            row["table"]
            for row in self.connection.execute("PRAGMA foreign_key_list('clases')")
        }
        self.assertEqual(
            class_fk_tables,
            {"actividad_sede", "entrenador_sede"},
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
                "idx_entrenador_sede_sede_id",
                "idx_actividad_sede_sede_id",
                "idx_disponibilidad_sede_dia",
                "idx_clases_sede_inicio_utc",
                "idx_clases_entrenador_sede_inicio_utc",
                "idx_clases_actividad_sede_inicio_utc",
            }.issubset(indexes)
        )
    def test_activity_and_site_form_a_unique_many_to_many_relation(self):
        other_site = self.insert_site("Oeste")
        self.insert_activity_site(self.activity_one, other_site)
        self.insert_activity_site(self.activity_two, self.site_one)
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM actividad_sede WHERE sede_id = ?",
                (self.site_one,),
            ).fetchone()[0],
            2,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_activity_site(self.activity_one, self.site_one)
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_activity("yoga")
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_activity_site(self.activity_one, self.site_one, enabled=2)
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_activity_site(99999, self.site_one)
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_activity_site(self.activity_one, 99999)

    def test_trainer_and_site_form_a_unique_many_to_many_relation(self):
        other_trainer = self.insert_trainer("otro.entrenador", "otro@example.com")
        self.insert_trainer_site(self.trainer_id, self.site_two, active=1)
        self.insert_trainer_site(other_trainer, self.site_one, active=0)
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM entrenador_sede WHERE entrenador_id = ?",
                (self.trainer_id,),
            ).fetchone()[0],
            2,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_trainer_site(self.trainer_id, self.site_one)
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_trainer_site(self.trainer_id, self.site_unlinked, active=2)
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_trainer_site(99999, self.site_one)
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_trainer_site(self.trainer_id, 99999)

    def test_classes_require_enabled_activity_and_active_trainer_site_links(self):
        self.assertGreater(self.insert_class(), 0)

        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_class(site_id=self.site_two)
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_class(
                activity_id=self.activity_two,
                site_id=self.site_one,
            )
        unlinked_trainer = self.insert_trainer(
            "sin.sede",
            "sin.sede@example.com",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_class(
                activity_id=self.activity_two,
                site_id=self.site_two,
                trainer_id=unlinked_trainer,
            )


        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_class(
                activity_id=self.activity_two,
                site_id=self.site_two,
                trainer_id=self.trainer_id,
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_class(site_id=self.site_unlinked)

        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(),
            [],
        )

    def test_class_update_cannot_assign_disabled_activity_or_unlinked_trainer(self):
        class_id = self.insert_class()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE clases SET sede_id = ? WHERE id_clase = ?",
                (self.site_two, class_id),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE clases SET entrenador_id = ? WHERE id_clase = ?",
                (99999, class_id),
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT sede_id FROM clases WHERE id_clase = ?",
                (class_id,),
            ).fetchone()[0],
            self.site_one,
        )

    def test_class_timestamps_capacity_and_status_are_constrained(self):
        self.insert_class()
        invalid_values = (
            {"start": "2026-08-10 12:00:00"},
            {"start": "2026-02-30T12:00:00Z"},
            {"start": "2026-08-10T24:00:00Z"},
            {"end": "2026-08-10T12:00:00Z"},
            {"end": "2026-08-10T11:59:59Z"},
            {"capacity": 0},
            {"capacity": -1},
            {"state": "pendiente"},
        )
        for values in invalid_values:
            with self.subTest(values=values), self.assertRaises(sqlite3.IntegrityError):
                self.insert_class(**values)

        class_id = self.insert_class(state="cancelada", capacity=1)
        self.assertEqual(
            self.connection.execute(
                "SELECT estado, cupo_maximo FROM clases WHERE id_clase = ?",
                (class_id,),
            ).fetchone()[:],
            ("cancelada", 1),
        )

    def test_availability_requires_valid_day_time_and_unique_slots(self):
        valid = ("09:00", "10:30")
        self.connection.execute(
            """
            INSERT INTO disponibilidad_entrenador
                (entrenador_id, sede_id, dia_semana, hora_inicio, hora_fin)
            VALUES (?, ?, ?, ?, ?)
            """,
            (self.trainer_id, self.site_one, 1, *valid),
        )
        invalid_slots = (
            (0, "09:00", "10:00"),
            (8, "09:00", "10:00"),
            (2, "9:00", "10:00"),
            (2, "24:00", "25:00"),
            (2, "10:00", "10:00"),
            (2, "11:00", "10:00"),
        )
        for day, start, end in invalid_slots:
            with self.subTest(day=day, start=start, end=end), self.assertRaises(
                sqlite3.IntegrityError
            ):
                self.connection.execute(
                    """
                    INSERT INTO disponibilidad_entrenador
                        (entrenador_id, sede_id, dia_semana, hora_inicio, hora_fin)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (self.trainer_id, self.site_one, day, start, end),
                )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO disponibilidad_entrenador
                    (entrenador_id, sede_id, dia_semana, hora_inicio, hora_fin)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self.trainer_id, self.site_one, 1, *valid),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO disponibilidad_entrenador
                    (entrenador_id, sede_id, dia_semana, hora_inicio, hora_fin)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self.trainer_id, self.site_unlinked, 1, "09:00", "10:00"),
            )

    def test_all_migrations_remain_idempotent_and_foreign_keys_are_valid(self):
        # El fixture inserta datos; confirmarlos permite probar el migrador fuera de una transacción.
        self.connection.commit()
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(apply_migrations(self.connection, MIGRATIONS_DIR), ())
        self.assertEqual(
            self.connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0],
            6,
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(),
            [],
        )


if __name__ == "__main__":
    unittest.main()
