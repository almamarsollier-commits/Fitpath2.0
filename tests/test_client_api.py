import tempfile
import unittest
from pathlib import Path

from backend.fitpath import create_app
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.seeds import seed_initial_permissions, seed_initial_roles


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPOSITORY_ROOT / "backend" / "fitpath" / "migrations"


class ClientApiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database_path = Path(temporary.name) / "client-api.sqlite3"
        self.app = create_app(
            "testing",
            {
                "DATABASE": str(self.database_path),
                "MIGRATIONS_DIR": str(MIGRATIONS_DIR),
                "SECRET_KEY": "client-api-test-secret",
            },
        )
        self.client = self.app.test_client()
        self.db = connect_database(self.database_path)
        self.addCleanup(self.db.close)
        self.assertEqual(apply_migrations(self.db, MIGRATIONS_DIR), tuple(range(1, 13)))
        seed_initial_roles(self.db)
        seed_initial_permissions(self.db)
        self.client_user_id = self._user("Cliente", "cliente-api", "client-api@example.test")
        self.other_user_id = self._user("Cliente", "otro-api", "other-api@example.test")
        self.trainer_user_id = self._user("Entrenador", "trainer-api", "trainer-api@example.test")
        self.admin_user_id = self._user("Administrador", "admin-api", "admin-api@example.test")
        self.client_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (self.client_user_id,)
        ).lastrowid
        self.other_client_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (self.other_user_id,)
        ).lastrowid
        self.site_id = self.db.execute(
            "INSERT INTO sedes (nombre, direccion, zona_horaria) VALUES ('Centro', 'Av. Central 100', 'America/Argentina/Buenos_Aires')"
        ).lastrowid
        self.trainer_id = self.db.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, 'Fuerza')",
            (self.trainer_user_id,),
        ).lastrowid
        self.db.execute(
            "INSERT INTO entrenador_sede (entrenador_id, sede_id, activo) VALUES (?, ?, 1)",
            (self.trainer_id, self.site_id),
        )
        self.activity_id = self.db.execute(
            "INSERT INTO actividades (nombre) VALUES ('Funcional')"
        ).lastrowid
        self.db.execute(
            "INSERT INTO actividad_sede (actividad_id, sede_id, habilitada) VALUES (?, ?, 1)",
            (self.activity_id, self.site_id),
        )
        self.class_id = self._class("2035-01-10T18:00:00Z", "2035-01-10T19:00:00Z", 2)
        self.full_class_id = self._class("2035-01-11T18:00:00Z", "2035-01-11T19:00:00Z", 1)
        self.past_class_id = self._class("2020-01-10T18:00:00Z", "2020-01-10T19:00:00Z", 10, "realizada")
        self.db.execute(
            "INSERT INTO inscripciones (cliente_id, clase_id, fecha_utc, estado) VALUES (?, ?, '2030-01-01T00:00:00Z', 'activa')",
            (self.other_client_id, self.full_class_id),
        )
        self.routine_id = self.db.execute(
            """
            INSERT INTO rutinas
                (nombre, descripcion, fecha_creacion_utc, entrenador_id, cliente_id, observaciones_entrenador)
            VALUES ('Fuerza inicial', 'Plan progresivo', '2030-01-01T00:00:00Z', ?, ?, 'Priorizar técnica')
            """,
            (self.trainer_id, self.client_id),
        ).lastrowid
        exercise_id = self.db.execute(
            "INSERT INTO ejercicios (nombre, grupo_muscular, descripcion) VALUES ('Sentadilla', 'Piernas', 'Movimiento controlado')"
        ).lastrowid
        self.db.execute(
            """
            INSERT INTO rutina_ejercicio
                (rutina_id, ejercicio_id, orden, series, repeticiones, peso_gramos, descanso_segundos)
            VALUES (?, ?, 1, 3, 10, 20000, 90)
            """,
            (self.routine_id, exercise_id),
        )
        self.db.execute(
            """
            INSERT INTO rutinas
                (nombre, fecha_creacion_utc, entrenador_id, cliente_id)
            VALUES ('Rutina ajena', '2030-01-02T00:00:00Z', ?, ?)
            """,
            (self.trainer_id, self.other_client_id),
        )
        self.db.commit()

    def _role(self, name):
        return self.db.execute(
            "SELECT id_rol FROM roles WHERE nombre = ?", (name,)
        ).fetchone()[0]

    def _user(self, role, username, email):
        return self.db.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES (?, 'Prueba', ?, ?, ?, 1)
            """,
            (role, username, email, self._role(role)),
        ).lastrowid

    def _class(self, start, end, capacity, status="programada"):
        return self.db.execute(
            """
            INSERT INTO clases
                (actividad_id, sede_id, entrenador_id, inicio_utc, fin_utc, cupo_maximo, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.activity_id,
                self.site_id,
                self.trainer_id,
                start,
                end,
                capacity,
                status,
            ),
        ).lastrowid

    def _login(self, user_id=None, csrf="client-api-csrf"):
        with self.client.session_transaction() as session:
            session["fitpath_user_id"] = user_id or self.client_user_id
            session["csrf_token"] = csrf

    def test_client_endpoints_require_session_role_and_persisted_permission(self):
        self.assertEqual(self.client.get("/api/v1/client/classes").status_code, 401)
        self._login(self.admin_user_id)
        self.assertEqual(self.client.get("/api/v1/client/classes").status_code, 403)
        self._login()
        self.db.execute("DELETE FROM rol_permiso")
        self.db.commit()
        self.assertEqual(self.client.get("/api/v1/client/classes").status_code, 403)

    def test_classes_show_capacity_and_only_own_enrollment(self):
        self._login()
        response = self.client.get("/api/v1/client/classes")
        self.assertEqual(response.status_code, 200)
        classes = {item["id"]: item for item in response.json["classes"]}
        self.assertNotIn(self.past_class_id, classes)
        self.assertFalse(classes[self.class_id]["inscripto"])
        self.assertEqual(classes[self.full_class_id]["cupos_disponibles"], 0)
        self.assertNotIn("entrenador", classes[self.class_id])

    def test_enrollment_and_cancellation_are_owned_csrf_protected_and_historical(self):
        self._login()
        missing_csrf = self.client.post(
            f"/api/v1/client/classes/{self.class_id}/enrollment"
        )
        self.assertEqual(missing_csrf.status_code, 400)
        enrolled = self.client.post(
            f"/api/v1/client/classes/{self.class_id}/enrollment",
            headers={"X-CSRF-Token": "client-api-csrf"},
        )
        self.assertEqual(enrolled.status_code, 201)
        repeated = self.client.post(
            f"/api/v1/client/classes/{self.class_id}/enrollment",
            headers={"X-CSRF-Token": "client-api-csrf"},
        )
        self.assertEqual(repeated.status_code, 409)
        full = self.client.post(
            f"/api/v1/client/classes/{self.full_class_id}/enrollment",
            headers={"X-CSRF-Token": "client-api-csrf"},
        )
        self.assertEqual(full.status_code, 409)

        cancelled = self.client.delete(
            f"/api/v1/client/classes/{self.class_id}/enrollment",
            headers={"X-CSRF-Token": "client-api-csrf"},
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(
            self.db.execute(
                "SELECT estado FROM inscripciones WHERE id_inscripcion = ?",
                (enrolled.json["enrollment"]["id"],),
            ).fetchone()[0],
            "cancelada",
        )
        self.assertEqual(
            self.client.delete(
                f"/api/v1/client/classes/{self.class_id}/enrollment",
                headers={"X-CSRF-Token": "client-api-csrf"},
            ).status_code,
            404,
        )

    def test_routines_include_exercises_and_never_return_other_client_data(self):
        self._login()
        response = self.client.get("/api/v1/client/routines")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["routines"]), 1)
        routine = response.json["routines"][0]
        self.assertEqual(routine["nombre"], "Fuerza inicial")
        self.assertEqual(routine["ejercicios"][0]["nombre"], "Sentadilla")
        self.assertEqual(routine["ejercicios"][0]["peso_gramos"], 20000)

    def test_progress_validation_creation_history_and_ownership(self):
        self._login()
        self.assertEqual(
            self.client.post(
                "/api/v1/client/progress",
                json={},
                headers={"X-CSRF-Token": "client-api-csrf"},
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/client/progress",
                json={"peso_kg": 10},
                headers={"X-CSRF-Token": "client-api-csrf"},
            ).status_code,
            400,
        )
        created = self.client.post(
            "/api/v1/client/progress",
            json={
                "peso_kg": 72.45,
                "porcentaje_grasa": 18.2,
                "rendimiento_ejercicios": "Sentadilla: 3 x 10",
                "observaciones": "Sesión estable",
            },
            headers={"X-CSRF-Token": "client-api-csrf"},
        )
        self.assertEqual(created.status_code, 201)
        history = self.client.get("/api/v1/client/progress")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json["progress"]), 1)
        self.assertEqual(history.json["progress"][0]["peso_kg"], 72.45)
        self.assertEqual(
            self.db.execute(
                "SELECT cliente_id FROM progresos WHERE id_progreso = ?",
                (created.json["progress"]["id"],),
            ).fetchone()[0],
            self.client_id,
        )

    def test_dashboard_uses_persisted_counts_and_next_own_class(self):
        self._login()
        self.client.post(
            f"/api/v1/client/classes/{self.class_id}/enrollment",
            headers={"X-CSRF-Token": "client-api-csrf"},
        )
        response = self.client.get("/api/v1/client/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["next_class"]["id"], self.class_id)
        self.assertEqual(response.json["counts"]["inscripciones"], 1)
        self.assertEqual(response.json["counts"]["rutinas"], 1)


if __name__ == "__main__":
    unittest.main()
