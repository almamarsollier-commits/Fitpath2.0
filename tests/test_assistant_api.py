"""Pruebas de lecturas reales y autorizadas para Smart Assistant."""

import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from backend.fitpath import create_app
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.permissions import CLIENT_DATA_PERMISSION
from backend.fitpath.seeds import (
    seed_initial_currencies,
    seed_initial_permissions,
    seed_initial_roles,
)


class AssistantApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "assistant.sqlite3"
        self.app = create_app(
            "testing",
            {"DATABASE": str(self.database_path), "SECRET_KEY": "assistant-test-only"},
        )
        self.client = self.app.test_client()
        self.db = connect_database(self.database_path)
        self.addCleanup(self.db.close)
        apply_migrations(self.db, self.app.config["MIGRATIONS_DIR"])
        seed_initial_roles(self.db)
        seed_initial_permissions(self.db)
        seed_initial_currencies(self.db)
        self._create_fixtures()

    def _role_id(self, name):
        return self.db.execute(
            "SELECT id_rol FROM roles WHERE nombre = ?", (name,)
        ).fetchone()[0]

    def _user(self, name, username, role):
        return self.db.execute(
            """
            INSERT INTO usuarios (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES (?, 'Prueba', ?, ?, ?, 1)
            """,
            (name, username, f"{username}@example.test", self._role_id(role)),
        ).lastrowid

    def _create_fixtures(self):
        self.client_user_id = self._user("Ana", "ana-assistant", "Cliente")
        self.other_user_id = self._user("Otra", "otra-assistant", "Cliente")
        self.admin_user_id = self._user("Ada", "admin-assistant", "Administrador")
        trainer_user_id = self._user("Tito", "trainer-assistant", "Entrenador")
        self.client_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (self.client_user_id,)
        ).lastrowid
        other_client_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (self.other_user_id,)
        ).lastrowid
        trainer_id = self.db.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, 'Fuerza')",
            (trainer_user_id,),
        ).lastrowid
        site_id = self.db.execute(
            "INSERT INTO sedes (nombre, direccion, zona_horaria) VALUES ('Centro', 'Calle 1', 'America/Argentina/Buenos_Aires')"
        ).lastrowid
        self.db.execute(
            "INSERT INTO entrenador_sede (entrenador_id, sede_id, activo) VALUES (?, ?, 1)",
            (trainer_id, site_id),
        )
        activity_id = self.db.execute(
            "INSERT INTO actividades (nombre) VALUES ('Funcional')"
        ).lastrowid
        self.db.execute(
            "INSERT INTO actividad_sede (actividad_id, sede_id, habilitada) VALUES (?, ?, 1)",
            (activity_id, site_id),
        )
        starts = datetime.now(timezone.utc) + timedelta(days=2)
        ends = starts + timedelta(hours=1)
        self.class_id = self.db.execute(
            """
            INSERT INTO clases
                (actividad_id, sede_id, entrenador_id, inicio_utc, fin_utc, cupo_maximo, estado)
            VALUES (?, ?, ?, ?, ?, 2, 'programada')
            """,
            (
                activity_id,
                site_id,
                trainer_id,
                starts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ends.strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        ).lastrowid
        self.db.execute(
            """
            INSERT INTO inscripciones (cliente_id, clase_id, fecha_utc, estado)
            VALUES (?, ?, ?, 'activa')
            """,
            (
                other_client_id,
                self.class_id,
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        )
        created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.routine_id = self.db.execute(
            """
            INSERT INTO rutinas (nombre, fecha_creacion_utc, entrenador_id, cliente_id)
            VALUES ('Base real', ?, ?, ?)
            """,
            (created, trainer_id, self.client_id),
        ).lastrowid
        self.db.execute(
            """
            INSERT INTO rutinas (nombre, fecha_creacion_utc, entrenador_id, cliente_id)
            VALUES ('Rutina ajena', ?, ?, ?)
            """,
            (created, trainer_id, other_client_id),
        )
        exercise_id = self.db.execute(
            "INSERT INTO ejercicios (nombre) VALUES ('Sentadilla')"
        ).lastrowid
        self.db.execute(
            """
            INSERT INTO rutina_ejercicio
                (rutina_id, ejercicio_id, orden, series, repeticiones, descanso_segundos)
            VALUES (?, ?, 1, 3, 10, 90)
            """,
            (self.routine_id, exercise_id),
        )
        self.progress_id = self.db.execute(
            "INSERT INTO progresos (cliente_id, fecha_utc, peso_kg) VALUES (?, ?, 70.5)",
            (self.client_id, created),
        ).lastrowid
        self.db.execute(
            "INSERT INTO progresos (cliente_id, fecha_utc, peso_kg) VALUES (?, ?, 99.0)",
            (other_client_id, created),
        )
        membership_id = self.db.execute(
            """
            INSERT INTO membresias
                (nombre, precio_unidades_menores, moneda, activa)
            VALUES ('Premium real', 10000, 'ARS', 1)
            """
        ).lastrowid
        self.membership_record_id = self.db.execute(
            """
            INSERT INTO cliente_membresia
                (cliente_id, membresia_id, fecha_inicio, estado)
            VALUES (?, ?, ?, 'activa')
            """,
            (self.client_id, membership_id, date.today().isoformat()),
        ).lastrowid
        self.db.commit()

    def _authenticate(self, user_id=None):
        with self.client.session_transaction() as session:
            session["fitpath_user_id"] = user_id or self.client_user_id
            session["csrf_token"] = "assistant-api-csrf"

    def test_requires_session_role_and_persisted_permission(self):
        response = self.client.get("/api/v1/assistant/classes")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["error"], "authentication_required")

        self._authenticate(self.admin_user_id)
        self.assertEqual(
            self.client.get("/api/v1/assistant/classes").status_code, 403
        )

        self._authenticate()
        permission_id = self.db.execute(
            "SELECT id_permiso FROM permisos WHERE clave = ?",
            (CLIENT_DATA_PERMISSION,),
        ).fetchone()[0]
        self.db.execute("DELETE FROM rol_permiso WHERE permiso_id = ?", (permission_id,))
        self.db.commit()
        self.assertEqual(
            self.client.get("/api/v1/assistant/classes").status_code, 403
        )

    def test_reads_real_classes_and_only_own_private_data(self):
        self._authenticate()
        classes = self.client.get("/api/v1/assistant/classes")
        self.assertEqual(classes.status_code, 200)
        self.assertIn("no-store", classes.headers["Cache-Control"])
        self.assertEqual(len(classes.json["classes"]), 1)
        self.assertEqual(classes.json["classes"][0]["id"], self.class_id)
        self.assertEqual(classes.json["classes"][0]["available_spots"], 1)
        self.assertFalse(classes.json["classes"][0]["enrollment_available"])
        self.assertNotIn("trainer", classes.json["classes"][0])

        routine = self.client.get("/api/v1/assistant/routine").json["routine"]
        self.assertEqual(routine["id"], self.routine_id)
        self.assertEqual(routine["exercise_count"], 1)
        progress = self.client.get("/api/v1/assistant/progress").json["progress"]
        self.assertEqual(progress["id"], self.progress_id)
        membership = self.client.get("/api/v1/assistant/membership").json["membership"]
        self.assertEqual(membership["id"], self.membership_record_id)
        self.assertEqual(membership["name"], "Premium real")

    def test_capabilities_disable_unvalidated_mutations_and_no_data_changes(self):
        self._authenticate()
        capabilities = self.client.get("/api/v1/assistant/capabilities")
        self.assertEqual(capabilities.status_code, 200)
        self.assertEqual(capabilities.json["write"], [])
        self.assertIn("enrollments.create", capabilities.json["disabled"])
        before = self.db.execute("SELECT count(*) FROM inscripciones").fetchone()[0]
        response = self.client.post(
            "/api/v1/assistant/enrollments", json={"clase_id": self.class_id}
        )
        self.assertIn(response.status_code, (404, 405))
        after = self.db.execute("SELECT count(*) FROM inscripciones").fetchone()[0]
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
