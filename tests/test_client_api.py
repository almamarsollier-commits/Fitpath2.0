import tempfile
import unittest
from pathlib import Path

from backend.fitpath import create_app
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.seeds import seed_initial_permissions, seed_initial_roles


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPOSITORY_ROOT / "backend" / "fitpath" / "migrations"
CLIENT_DATA_SCRIPT = (
    REPOSITORY_ROOT / "statics" / "js" / "modules" / "client-data.js"
)
TRAINING_VIEW = (
    REPOSITORY_ROOT / "templates" / "cliente" / "rutina" / "entrenamiento.html"
)
EXERCISE_VIEW = (
    REPOSITORY_ROOT / "templates" / "cliente" / "rutina" / "ejercicio.html"
)
CLASS_DETAIL_VIEW = (
    REPOSITORY_ROOT / "templates" / "cliente" / "clases" / "detalle.html"
)
ACTIVITY_VIEW = (
    REPOSITORY_ROOT / "templates" / "cliente" / "inicio" / "actividad.html"
)
NEXT_CLASS_VIEW = (
    REPOSITORY_ROOT / "templates" / "cliente" / "inicio" / "proxima-clase.html"
)
EVOLUTION_VIEW = (
    REPOSITORY_ROOT / "templates" / "cliente" / "progreso" / "evolucion.html"
)


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
        self.assertEqual(apply_migrations(self.db, MIGRATIONS_DIR), tuple(range(1, 15)))
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
        self.db.execute("INSERT INTO monedas (codigo, decimales) VALUES ('ARS', 2)")
        self.membership_id = self.db.execute(
            """
            INSERT INTO membresias
                (nombre, precio_unidades_menores, moneda, descripcion, activa)
            VALUES ('Acceso Cliente API', 0, 'ARS', 'Plan de pruebas', 1)
            """
        ).lastrowid
        self.subscription_id = self.db.execute(
            """
            INSERT INTO cliente_membresia
                (cliente_id, membresia_id, fecha_inicio, fecha_fin, estado)
            VALUES (?, ?, '2020-01-01', NULL, 'activa')
            """,
            (self.client_id, self.membership_id),
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
        objective_type_id = self.db.execute(
            "INSERT INTO tipos_objetivo (nombre) VALUES ('Fuerza Cliente API')"
        ).lastrowid
        self.objective_id = self.db.execute(
            """
            INSERT INTO objetivos (tipo_objetivo_id, nombre, descripcion)
            VALUES (?, 'Mejorar fuerza', 'Objetivo persistido')
            """,
            (objective_type_id,),
        ).lastrowid
        self.db.execute(
            "INSERT INTO cliente_objetivo (cliente_id, objetivo_id) VALUES (?, ?)",
            (self.client_id, self.objective_id),
        )
        self.routine_id = self.db.execute(
            """
            INSERT INTO rutinas
                (nombre, descripcion, fecha_creacion_utc, entrenador_id,
                 cliente_id, objetivo_id, observaciones_entrenador)
            VALUES ('Fuerza inicial', 'Plan progresivo', '2030-01-01T00:00:00Z',
                    ?, ?, ?, 'Priorizar técnica')
            """,
            (self.trainer_id, self.client_id, self.objective_id),
        ).lastrowid
        self.exercise_id = self.db.execute(
            "INSERT INTO ejercicios (nombre, grupo_muscular, descripcion) VALUES ('Sentadilla', 'Piernas', 'Movimiento controlado')"
        ).lastrowid
        self.assignment_id = self.db.execute(
            """
            INSERT INTO rutina_ejercicio
                (rutina_id, ejercicio_id, orden, series, repeticiones, peso_gramos, descanso_segundos)
            VALUES (?, ?, 1, 3, 10, 20000, 90)
            """,
            (self.routine_id, self.exercise_id),
        ).lastrowid
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
        self.assertEqual(self.client.get("/api/v1/client/routines").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/client/progress").status_code, 401)
        self._login(self.admin_user_id)
        self.assertEqual(self.client.get("/api/v1/client/classes").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/client/routines").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/client/progress").status_code, 403)
        self._login()
        self.db.execute("DELETE FROM rol_permiso")
        self.db.commit()
        self.assertEqual(self.client.get("/api/v1/client/classes").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/client/routines").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/client/progress").status_code, 403)

    def test_classes_show_capacity_and_only_own_enrollment(self):
        self._login()
        response = self.client.get("/api/v1/client/classes")
        self.assertEqual(response.status_code, 200)
        classes = {item["id"]: item for item in response.json["classes"]}
        self.assertNotIn(self.past_class_id, classes)
        self.assertFalse(classes[self.class_id]["inscripto"])
        self.assertEqual(classes[self.full_class_id]["cupos_disponibles"], 0)
        self.assertIsNone(classes[self.full_class_id]["inscripcion_id"])
        self.assertEqual(classes[self.class_id]["entrenador"], "Entrenador Prueba")
        self.assertEqual(classes[self.class_id]["entrenador_especialidad"], "Fuerza")

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

    def test_enrollment_requires_an_active_current_membership(self):
        self.db.execute(
            "UPDATE cliente_membresia SET estado = 'vencida' WHERE id_cliente_membresia = ?",
            (self.subscription_id,),
        )
        self.db.commit()
        self._login()
        response = self.client.post(
            f"/api/v1/client/classes/{self.class_id}/enrollment",
            headers={"X-CSRF-Token": "client-api-csrf"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["error"], "active_membership_required")
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM inscripciones WHERE cliente_id = ?", (self.client_id,)).fetchone()[0],
            0,
        )
        self.assertIn(
            "active_membership_required",
            CLIENT_DATA_SCRIPT.read_text(encoding="utf-8"),
        )

    def test_routines_include_exercises_and_never_return_other_client_data(self):
        self._login()
        response = self.client.get("/api/v1/client/routines")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["routines"]), 1)
        routine = response.json["routines"][0]
        self.assertEqual(routine["nombre"], "Fuerza inicial")
        self.assertEqual(routine["objetivo"], "Mejorar fuerza")
        self.assertEqual(routine["activa"], 1)
        exercise = routine["ejercicios"][0]
        self.assertEqual(exercise["asignacion_id"], self.assignment_id)
        self.assertEqual(exercise["id"], self.exercise_id)
        self.assertEqual(exercise["nombre"], "Sentadilla")
        self.assertEqual(
            (
                exercise["series"],
                exercise["repeticiones"],
                exercise["peso_gramos"],
                exercise["descanso_segundos"],
            ),
            (3, 10, 20000, 90),
        )

    def test_routine_navigation_uses_owned_payload_and_existing_progress(self):
        script = CLIENT_DATA_SCRIPT.read_text(encoding="utf-8")
        training = TRAINING_VIEW.read_text(encoding="utf-8")
        exercise = EXERCISE_VIEW.read_text(encoding="utf-8")
        self.assertIn('api("/api/v1/client/routines")', script)
        self.assertIn("exercise.asignacion_id", script)
        self.assertIn('positiveQueryParameter("rutina")', script)
        self.assertIn('positiveQueryParameter("asignacion")', script)
        self.assertIn("data-client-training-root", training)
        self.assertIn("data-client-exercise-root", exercise)
        self.assertIn("/templates/cliente/progreso/index.html", training)
        self.assertIn("/templates/cliente/progreso/index.html", exercise)
        self.assertNotIn("fictici", training.lower())
        self.assertNotIn("fictici", exercise.lower())

    def test_class_activity_and_evolution_views_use_existing_owned_endpoints(self):
        script = CLIENT_DATA_SCRIPT.read_text(encoding="utf-8")
        views = {
            "data-client-class-detail-root": CLASS_DETAIL_VIEW,
            "data-client-activity-root": ACTIVITY_VIEW,
            "data-client-next-class-root": NEXT_CLASS_VIEW,
            "data-client-evolution-root": EVOLUTION_VIEW,
        }
        for marker, path in views.items():
            content = path.read_text(encoding="utf-8")
            self.assertIn(marker, content)
            self.assertNotIn("fictici", content.lower())
        self.assertIn('positiveQueryParameter("clase")', script)
        self.assertIn('api("/api/v1/client/classes")', script)
        self.assertIn('api("/api/v1/client/enrollments")', script)
        self.assertIn('api("/api/v1/client/progress")', script)
        self.assertIn('"X-CSRF-Token": csrfToken', script)
        self.assertIn("function progressChart", script)

    def test_progress_validation_creation_history_and_ownership(self):
        self._login()
        self.assertEqual(
            self.client.post(
                "/api/v1/client/progress",
                json={"peso_kg": 72},
            ).status_code,
            400,
        )
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
        self.db.execute(
            """
            INSERT INTO progresos (cliente_id, fecha_utc, peso_kg, observaciones)
            VALUES (?, '2031-01-01T00:00:00Z', 90, 'Registro ajeno')
            """,
            (self.other_client_id,),
        )
        self.db.commit()
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
