import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.fitpath import create_app
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.permissions import (
    ADMIN_DATA_PERMISSION,
    ADMIN_VIEWS_PERMISSION,
    CLIENT_DATA_PERMISSION,
    CLIENT_VIEWS_PERMISSION,
)
from backend.fitpath.seeds import (
    seed_initial_currencies,
    seed_initial_permissions,
    seed_initial_roles,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPOSITORY_ROOT / "backend" / "fitpath" / "migrations"
ROLE_DASHBOARD_SCRIPT = REPOSITORY_ROOT / "statics" / "js" / "modules" / "role-dashboard.js"
TRAINER_ROUTINES_SCRIPT = REPOSITORY_ROOT / "statics" / "js" / "modules" / "trainer-routines.js"
TRAINER_ATTENDANCE_SCRIPT = REPOSITORY_ROOT / "statics" / "js" / "modules" / "trainer-attendance.js"


class RoleApiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database_path = Path(temporary.name) / "roles.sqlite3"
        self.app = create_app(
            "testing",
            {
                "DATABASE": str(self.database_path),
                "MIGRATIONS_DIR": str(MIGRATIONS_DIR),
                "SECRET_KEY": "roles-test-secret",
            },
        )
        self.client = self.app.test_client()
        self.db = connect_database(self.database_path)
        self.addCleanup(self.db.close)
        apply_migrations(self.db, MIGRATIONS_DIR)
        seed_initial_roles(self.db)
        seed_initial_permissions(self.db)
        seed_initial_currencies(self.db)

        self.client_user = self._user("Cliente", "role-client")
        self.other_client_user = self._user("Cliente", "role-other-client")
        self.trainer_user = self._user("Entrenador", "role-trainer")
        self.manager_user = self._user("Jefe de sede", "role-manager")
        self.admin_user = self._user("Administrador", "role-admin")
        self.technician_user = self._user("Técnico de mantenimiento", "role-tech")
        self.other_technician_user = self._user("Técnico de mantenimiento", "role-tech-other")

        self.client_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (self.client_user,)
        ).lastrowid
        self.other_client_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (self.other_client_user,)
        ).lastrowid
        self.site_id = self.db.execute(
            "INSERT INTO sedes (nombre, direccion, zona_horaria) VALUES ('Centro Roles', 'Calle 1', 'America/Argentina/Buenos_Aires')"
        ).lastrowid
        self.other_site_id = self.db.execute(
            "INSERT INTO sedes (nombre, direccion, zona_horaria) VALUES ('Norte Roles', 'Calle 2', 'America/Argentina/Buenos_Aires')"
        ).lastrowid
        self.trainer_id = self.db.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, 'Fuerza')",
            (self.trainer_user,),
        ).lastrowid
        self.db.execute(
            "INSERT INTO entrenador_sede (entrenador_id, sede_id, activo) VALUES (?, ?, 1)",
            (self.trainer_id, self.site_id),
        )
        self.manager_id = self.db.execute(
            "INSERT INTO jefes_sede (usuario_id, sede_id) VALUES (?, ?)",
            (self.manager_user, self.site_id),
        ).lastrowid
        self.technician_id = self.db.execute(
            "INSERT INTO tecnicos_mantenimiento (usuario_id, sede_id) VALUES (?, ?)",
            (self.technician_user, self.site_id),
        ).lastrowid
        self.other_technician_id = self.db.execute(
            "INSERT INTO tecnicos_mantenimiento (usuario_id, sede_id) VALUES (?, ?)",
            (self.other_technician_user, self.other_site_id),
        ).lastrowid
        self.activity_id = self.db.execute(
            "INSERT INTO actividades (nombre) VALUES ('Funcional Roles')"
        ).lastrowid
        self.db.execute(
            "INSERT INTO actividad_sede (actividad_id, sede_id, habilitada) VALUES (?, ?, 1)",
            (self.activity_id, self.site_id),
        )
        self.past_class = self._class(
            self.site_id, "2025-01-01T10:00:00Z", "2025-01-01T11:00:00Z", 3
        )
        self.future_class = self._class(
            self.site_id, "2035-01-01T10:00:00Z", "2035-01-01T11:00:00Z", 3
        )
        self.other_class = self._class(
            self.other_site_id,
            "2035-02-01T10:00:00Z",
            "2035-02-01T11:00:00Z",
            4,
            link=True,
        )
        self.past_enrollment = self.db.execute(
            "INSERT INTO inscripciones (cliente_id, clase_id, fecha_utc, estado) VALUES (?, ?, '2024-12-01T00:00:00Z', 'activa')",
            (self.client_id, self.past_class),
        ).lastrowid
        self.db.execute(
            "INSERT INTO inscripciones (cliente_id, clase_id, fecha_utc, estado) VALUES (?, ?, '2030-01-01T00:00:00Z', 'activa')",
            (self.client_id, self.future_class),
        )
        self.db.execute(
            "INSERT INTO inscripciones (cliente_id, clase_id, fecha_utc, estado) VALUES (?, ?, '2030-01-01T00:00:01Z', 'activa')",
            (self.other_client_id, self.future_class),
        )
        self.machine_id = self.db.execute(
            "INSERT INTO maquinas (sede_id, tipo, estado) VALUES (?, 'Cinta', 'operativa')",
            (self.site_id,),
        ).lastrowid
        self.other_machine_id = self.db.execute(
            "INSERT INTO maquinas (sede_id, tipo, estado) VALUES (?, 'Bicicleta', 'operativa')",
            (self.other_site_id,),
        ).lastrowid
        self.db.commit()

    def _role_id(self, name):
        return self.db.execute(
            "SELECT id_rol FROM roles WHERE nombre = ?", (name,)
        ).fetchone()[0]

    def _user(self, role, username):
        return self.db.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES (?, 'Prueba', ?, ?, ?, 1)
            """,
            (role, username, f"{username}@example.test", self._role_id(role)),
        ).lastrowid

    def _class(self, site_id, start, end, capacity, link=False):
        if link:
            self.db.execute(
                "INSERT INTO entrenador_sede (entrenador_id, sede_id, activo) VALUES (?, ?, 1)",
                (self.trainer_id, site_id),
            )
            self.db.execute(
                "INSERT INTO actividad_sede (actividad_id, sede_id, habilitada) VALUES (?, ?, 1)",
                (self.activity_id, site_id),
            )
        return self.db.execute(
            """
            INSERT INTO clases
                (actividad_id, sede_id, entrenador_id, inicio_utc, fin_utc, cupo_maximo, estado)
            VALUES (?, ?, ?, ?, ?, ?, 'programada')
            """,
            (self.activity_id, site_id, self.trainer_id, start, end, capacity),
        ).lastrowid

    def _login(self, user_id, csrf="role-csrf"):
        with self.client.session_transaction() as session:
            session["fitpath_user_id"] = user_id
            session["csrf_token"] = csrf

    def _json(self):
        return {"X-CSRF-Token": "role-csrf"}

    def test_role_dashboards_require_matching_role_permission_and_profile(self):
        cases = (
            (self.trainer_user, "/auth/entrenador", "/api/v1/trainer/dashboard"),
            (self.manager_user, "/auth/jefe-sede", "/api/v1/manager/dashboard"),
            (self.admin_user, "/auth/administrador", "/api/v1/admin/dashboard"),
            (self.technician_user, "/auth/tecnico", "/api/v1/technician/dashboard"),
        )
        for user_id, view, api in cases:
            self._login(user_id)
            page = self.client.get(view)
            self.assertEqual(page.status_code, 200, view)
            self.assertIn(b"role-dashboard.js", page.data)
            self.assertEqual(self.client.get(api).status_code, 200, api)
        self._login(self.trainer_user)
        self.assertEqual(self.client.get("/api/v1/admin/dashboard").status_code, 403)
        self.assertEqual(self.client.get("/auth/administrador").status_code, 403)

    def test_trainer_routines_view_is_protected_and_uses_existing_apis(self):
        anonymous = self.client.get("/auth/entrenador/rutinas")
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn("/auth/login", anonymous.headers["Location"])

        self._login(self.trainer_user)
        page = self.client.get("/auth/entrenador/rutinas")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"trainer-routines.js", page.data)
        self.assertIn(b'aria-current="page"', page.data)
        self.assertIn(b"data-routine-content", page.data)

        dashboard = self.client.get("/auth/entrenador")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"/auth/entrenador/rutinas", dashboard.data)

        self._login(self.manager_user)
        self.assertEqual(self.client.get("/auth/entrenador/rutinas").status_code, 403)

        script = TRAINER_ROUTINES_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('requestJson("/api/v1/trainer/dashboard")', script)
        self.assertIn('"/api/v1/trainer/routines"', script)
        self.assertIn('"/api/v1/trainer/exercises"', script)
        self.assertIn("peso_gramos", script)
        self.assertIn('headers["X-CSRF-Token"] = state.csrfToken', script)
        self.assertIn("window.confirm", script)
        self.assertNotIn("ID de rutina", script)

    def test_trainer_attendance_view_is_protected_and_updates_without_duplicates(self):
        anonymous = self.client.get("/auth/entrenador/asistencias")
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn("/auth/login", anonymous.headers["Location"])

        self._login(self.trainer_user)
        page = self.client.get("/auth/entrenador/asistencias")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"trainer-attendance.js", page.data)
        self.assertIn(b'aria-current="page"', page.data)
        self.assertIn(b"data-attendance-content", page.data)
        dashboard_page = self.client.get("/auth/entrenador")
        self.assertIn(b"/auth/entrenador/asistencias", dashboard_page.data)

        first = self.client.post(
            "/api/v1/trainer/attendance",
            json={"inscripcion_id": self.past_enrollment, "estado": "presente"},
            headers=self._json(),
        )
        second = self.client.post(
            "/api/v1/trainer/attendance",
            json={"inscripcion_id": self.past_enrollment, "estado": "ausente"},
            headers=self._json(),
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        stored = self.db.execute(
            "SELECT estado FROM asistencias WHERE inscripcion_id = ?",
            (self.past_enrollment,),
        ).fetchall()
        self.assertEqual([row["estado"] for row in stored], ["ausente"])

        other_trainer_user = self._user("Entrenador", "attendance-other-trainer")
        other_trainer_id = self.db.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, 'Movilidad')",
            (other_trainer_user,),
        ).lastrowid
        self.db.execute(
            "INSERT INTO entrenador_sede (entrenador_id, sede_id, activo) VALUES (?, ?, 1)",
            (other_trainer_id, self.site_id),
        )
        foreign_class = self.db.execute(
            """
            INSERT INTO clases
                (actividad_id, sede_id, entrenador_id, inicio_utc, fin_utc,
                 cupo_maximo, estado)
            VALUES (?, ?, ?, '2025-02-01T10:00:00Z', '2025-02-01T11:00:00Z',
                    5, 'programada')
            """,
            (self.activity_id, self.site_id, other_trainer_id),
        ).lastrowid
        foreign_enrollment = self.db.execute(
            """
            INSERT INTO inscripciones (cliente_id, clase_id, fecha_utc, estado)
            VALUES (?, ?, '2025-01-01T00:00:00Z', 'activa')
            """,
            (self.other_client_id, foreign_class),
        ).lastrowid
        self.db.commit()
        denied = self.client.post(
            "/api/v1/trainer/attendance",
            json={"inscripcion_id": foreign_enrollment, "estado": "presente"},
            headers=self._json(),
        )
        self.assertEqual(denied.status_code, 404)
        self.assertIsNone(
            self.db.execute(
                "SELECT 1 FROM asistencias WHERE inscripcion_id = ?",
                (foreign_enrollment,),
            ).fetchone()
        )

        self._login(self.manager_user)
        self.assertEqual(self.client.get("/auth/entrenador/asistencias").status_code, 403)

        script = TRAINER_ATTENDANCE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('requestJson("/api/v1/trainer/dashboard")', script)
        self.assertIn('requestJson("/api/v1/trainer/attendance"', script)
        self.assertIn('headers["X-CSRF-Token"] = state.csrfToken', script)
        self.assertIn('input.type = "radio"', script)
        self.assertIn("item.puede_registrar", script)
        self.assertNotIn("ID de clase", script)

    def test_trainer_manages_only_authorized_students_classes_and_sites(self):
        self._login(self.trainer_user)
        created = self.client.post(
            "/api/v1/trainer/routines",
            json={"nombre": "Rutina autorizada", "cliente_id": self.client_id},
            headers=self._json(),
        )
        self.assertEqual(created.status_code, 201)
        routine_id = created.json["routine"]["id"]
        denied = self.client.post(
            "/api/v1/trainer/routines",
            json={"nombre": "Rutina ajena", "cliente_id": 999999},
            headers=self._json(),
        )
        self.assertEqual(denied.status_code, 403)
        exercise = self.client.post(
            "/api/v1/trainer/exercises",
            json={"nombre": "Peso muerto", "grupo_muscular": "Cadena posterior"},
            headers=self._json(),
        )
        self.assertEqual(exercise.status_code, 201)
        exercise_id = exercise.json["exercise"]["id"]
        edited = self.client.patch(
            f"/api/v1/trainer/routines/{routine_id}",
            json={"observaciones": "Controlar técnica y respiración"},
            headers=self._json(),
        )
        self.assertEqual(edited.status_code, 200)
        assigned = self.client.post(
            f"/api/v1/trainer/routines/{routine_id}/exercises",
            json={
                "ejercicio_id": exercise_id,
                "orden": 1,
                "series": 3,
                "repeticiones": 8,
                "peso_gramos": 20000,
                "descanso_segundos": 90,
            },
            headers=self._json(),
        )
        self.assertEqual(assigned.status_code, 201)
        availability = self.client.post(
            "/api/v1/trainer/availability",
            json={"sede_id": self.site_id, "dia_semana": 1, "hora_inicio": "08:00", "hora_fin": "12:00"},
            headers=self._json(),
        )
        self.assertEqual(availability.status_code, 201)
        attendance = self.client.post(
            "/api/v1/trainer/attendance",
            json={"inscripcion_id": self.past_enrollment, "estado": "presente"},
            headers=self._json(),
        )
        self.assertEqual(attendance.status_code, 200)
        self.assertEqual(
            self.db.execute(
                "SELECT estado FROM asistencias WHERE inscripcion_id = ?",
                (self.past_enrollment,),
            ).fetchone()[0],
            "presente",
        )

    def test_trainer_offers_attendance_only_when_class_has_started(self):
        self._login(self.trainer_user)
        future_enrollment = self.db.execute(
            "SELECT id_inscripcion FROM inscripciones WHERE cliente_id = ? AND clase_id = ?",
            (self.client_id, self.future_class),
        ).fetchone()[0]

        dashboard = self.client.get("/api/v1/trainer/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        eligible_ids = {
            item["id"] for item in dashboard.json["options"]["attendance_enrollments"]
        }
        self.assertIn(self.past_enrollment, eligible_ids)
        self.assertNotIn(future_enrollment, eligible_ids)
        past_option = next(
            item
            for item in dashboard.json["options"]["enrollments"]
            if item["id"] == self.past_enrollment
        )
        self.assertEqual(past_option["clase_id"], self.past_class)
        self.assertEqual(past_option["sede"], "Centro Roles")
        self.assertEqual(past_option["fin_utc"], "2025-01-01T11:00:00Z")

        missing_csrf = self.client.post(
            "/api/v1/trainer/attendance",
            json={"inscripcion_id": self.past_enrollment, "estado": "presente"},
        )
        self.assertEqual(missing_csrf.status_code, 400)
        self.assertIsNone(
            self.db.execute(
                "SELECT 1 FROM asistencias WHERE inscripcion_id = ?",
                (self.past_enrollment,),
            ).fetchone()
        )

        self.db.execute(
            "UPDATE clases SET estado = 'cancelada' WHERE id_clase = ?",
            (self.past_class,),
        )
        self.db.commit()
        cancelled = self.client.post(
            "/api/v1/trainer/attendance",
            json={"inscripcion_id": self.past_enrollment, "estado": "presente"},
            headers=self._json(),
        )
        self.assertEqual(cancelled.status_code, 409)
        self.assertEqual(cancelled.json["error"], "attendance_class_cancelled")

        refreshed = self.client.get("/api/v1/trainer/dashboard")
        refreshed_ids = {
            item["id"]
            for item in refreshed.json["options"]["attendance_enrollments"]
        }
        self.assertNotIn(self.past_enrollment, refreshed_ids)

        script = TRAINER_ATTENDANCE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("function classIsEnabled", script)
        self.assertIn("item.puede_registrar", script)
        self.assertNotIn("ID de inscripción", script)
        dashboard_script = ROLE_DASHBOARD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            '["trainer", "manager", "admin", "technician"].includes(role)',
            dashboard_script,
        )

    def test_trainer_deletes_only_own_safe_availability(self):
        self._login(self.trainer_user)
        created = self.client.post(
            "/api/v1/trainer/availability",
            json={
                "sede_id": self.site_id,
                "dia_semana": 1,
                "hora_inicio": "06:00",
                "hora_fin": "09:00",
            },
            headers=self._json(),
        )
        self.assertEqual(created.status_code, 201)
        availability_id = created.json["availability"]["id"]

        missing_csrf = self.client.delete(
            f"/api/v1/trainer/availability/{availability_id}"
        )
        self.assertEqual(missing_csrf.status_code, 400)
        self.assertIsNotNone(
            self.db.execute(
                "SELECT 1 FROM disponibilidad_entrenador WHERE id_disponibilidad = ?",
                (availability_id,),
            ).fetchone()
        )

        other_user = self._user("Entrenador", "role-other-trainer")
        other_trainer = self.db.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, 'Yoga')",
            (other_user,),
        ).lastrowid
        self.db.execute(
            "INSERT INTO entrenador_sede (entrenador_id, sede_id, activo) VALUES (?, ?, 1)",
            (other_trainer, self.site_id),
        )
        other_availability = self.db.execute(
            """
            INSERT INTO disponibilidad_entrenador
                (entrenador_id, sede_id, dia_semana, hora_inicio, hora_fin)
            VALUES (?, ?, 2, '10:00', '12:00')
            """,
            (other_trainer, self.site_id),
        ).lastrowid
        self.db.commit()
        foreign = self.client.delete(
            f"/api/v1/trainer/availability/{other_availability}",
            headers=self._json(),
        )
        self.assertEqual(foreign.status_code, 404)
        self.assertIsNotNone(
            self.db.execute(
                "SELECT 1 FROM disponibilidad_entrenador WHERE id_disponibilidad = ?",
                (other_availability,),
            ).fetchone()
        )

        scheduled_conflict = self.client.delete(
            f"/api/v1/trainer/availability/{availability_id}",
            headers=self._json(),
        )
        self.assertEqual(scheduled_conflict.status_code, 409)
        self.assertEqual(
            scheduled_conflict.json["error"],
            "availability_has_scheduled_classes",
        )

        replacement = self.client.post(
            "/api/v1/trainer/availability",
            json={
                "sede_id": self.site_id,
                "dia_semana": 1,
                "hora_inicio": "07:00",
                "hora_fin": "08:00",
            },
            headers=self._json(),
        )
        self.assertEqual(replacement.status_code, 201)
        replacement_id = replacement.json["availability"]["id"]
        deleted = self.client.delete(
            f"/api/v1/trainer/availability/{availability_id}",
            headers=self._json(),
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json, {"deleted": True})

        dashboard = self.client.get("/api/v1/trainer/dashboard")
        availability_rows = next(
            section["rows"]
            for section in dashboard.json["sections"]
            if section["title"] == "Disponibilidad"
        )
        self.assertIn(
            {
                "id": replacement_id,
                "sede_id": self.site_id,
                "sede": "Centro Roles",
                "dia_semana": 1,
                "hora_inicio": "07:00",
                "hora_fin": "08:00",
            },
            availability_rows,
        )

        self._login(self.manager_user)
        forbidden = self.client.delete(
            f"/api/v1/trainer/availability/{replacement_id}",
            headers=self._json(),
        )
        self.assertEqual(forbidden.status_code, 403)

        script = ROLE_DASHBOARD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("function trainerAvailabilityDelete", script)
        self.assertIn("window.confirm", script)
        self.assertIn(
            "`/api/v1/trainer/availability/${availability.id}`",
            script,
        )
        self.assertIn("rowActions.Disponibilidad", script)

    def test_trainer_manages_routine_exercises_objective_and_history(self):
        objective_type = self.db.execute(
            "INSERT INTO tipos_objetivo (nombre) VALUES ('Objetivo Rutinas')"
        ).lastrowid
        first_objective = self.db.execute(
            "INSERT INTO objetivos (tipo_objetivo_id, nombre) VALUES (?, 'Fuerza aplicada')",
            (objective_type,),
        ).lastrowid
        second_objective = self.db.execute(
            "INSERT INTO objetivos (tipo_objetivo_id, nombre) VALUES (?, 'Movilidad general')",
            (objective_type,),
        ).lastrowid
        foreign_objective = self.db.execute(
            "INSERT INTO objetivos (tipo_objetivo_id, nombre) VALUES (?, 'Objetivo ajeno')",
            (objective_type,),
        ).lastrowid
        self.db.executemany(
            "INSERT INTO cliente_objetivo (cliente_id, objetivo_id) VALUES (?, ?)",
            (
                (self.client_id, first_objective),
                (self.client_id, second_objective),
                (self.other_client_id, foreign_objective),
            ),
        )
        progress_id = self.db.execute(
            """
            INSERT INTO progresos (cliente_id, fecha_utc, observaciones)
            VALUES (?, '2030-01-01T00:00:00Z', 'Historial preservado')
            """,
            (self.client_id,),
        ).lastrowid
        self.db.commit()

        self._login(self.trainer_user)
        routine = self.client.post(
            "/api/v1/trainer/routines",
            json={
                "nombre": "Rutina gestionable",
                "cliente_id": self.client_id,
                "objetivo_id": first_objective,
            },
            headers=self._json(),
        )
        self.assertEqual(routine.status_code, 201)
        routine_id = routine.json["routine"]["id"]
        exercise_ids = []
        for name in ("Ejercicio A", "Ejercicio B"):
            created = self.client.post(
                "/api/v1/trainer/exercises",
                json={"nombre": name},
                headers=self._json(),
            )
            self.assertEqual(created.status_code, 201)
            exercise_ids.append(created.json["exercise"]["id"])
        assignment_ids = []
        for order, exercise_id in enumerate(exercise_ids, 1):
            assigned = self.client.post(
                f"/api/v1/trainer/routines/{routine_id}/exercises",
                json={
                    "ejercicio_id": exercise_id,
                    "orden": order,
                    "series": 3,
                    "repeticiones": 10,
                    "peso_gramos": 10000,
                    "descanso_segundos": 60,
                },
                headers=self._json(),
            )
            self.assertEqual(assigned.status_code, 201)
            assignment_ids.append(assigned.json["routine_exercise"]["id"])

        missing_csrf = self.client.patch(
            f"/api/v1/trainer/routines/{routine_id}/exercises/{assignment_ids[0]}",
            json={"series": 4},
        )
        self.assertEqual(missing_csrf.status_code, 400)
        updated = self.client.patch(
            f"/api/v1/trainer/routines/{routine_id}/exercises/{assignment_ids[0]}",
            json={
                "orden": 2,
                "series": 4,
                "repeticiones": 8,
                "peso_gramos": 25000,
                "descanso_segundos": 90,
            },
            headers=self._json(),
        )
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))
        ordered = self.db.execute(
            """
            SELECT id_rutina_ejercicio, orden FROM rutina_ejercicio
            WHERE rutina_id = ? ORDER BY orden
            """,
            (routine_id,),
        ).fetchall()
        self.assertEqual(
            [tuple(row) for row in ordered],
            [(assignment_ids[1], 1), (assignment_ids[0], 2)],
        )
        invalid_order = self.client.patch(
            f"/api/v1/trainer/routines/{routine_id}/exercises/{assignment_ids[0]}",
            json={"orden": 3},
            headers=self._json(),
        )
        self.assertEqual(invalid_order.status_code, 400)
        self.assertEqual(
            [
                tuple(row)
                for row in self.db.execute(
                    """
                    SELECT id_rutina_ejercicio, orden FROM rutina_ejercicio
                    WHERE rutina_id = ? ORDER BY orden
                    """,
                    (routine_id,),
                ).fetchall()
            ],
            [(assignment_ids[1], 1), (assignment_ids[0], 2)],
        )

        invalid_objective = self.client.patch(
            f"/api/v1/trainer/routines/{routine_id}",
            json={"objetivo_id": foreign_objective},
            headers=self._json(),
        )
        self.assertEqual(invalid_objective.status_code, 409)
        objective_updated = self.client.patch(
            f"/api/v1/trainer/routines/{routine_id}",
            json={"objetivo_id": second_objective},
            headers=self._json(),
        )
        self.assertEqual(objective_updated.status_code, 200)

        other_trainer_user = self._user("Entrenador", "routine-other-trainer")
        self.db.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, 'Resistencia')",
            (other_trainer_user,),
        )
        self.db.commit()
        self._login(other_trainer_user)
        foreign_edit = self.client.patch(
            f"/api/v1/trainer/routines/{routine_id}/exercises/{assignment_ids[0]}",
            json={"series": 9},
            headers=self._json(),
        )
        self.assertEqual(foreign_edit.status_code, 404)
        foreign_assignment_delete = self.client.delete(
            f"/api/v1/trainer/routines/{routine_id}/exercises/{assignment_ids[0]}",
            headers=self._json(),
        )
        self.assertEqual(foreign_assignment_delete.status_code, 404)
        foreign_deactivate = self.client.delete(
            f"/api/v1/trainer/routines/{routine_id}", headers=self._json()
        )
        self.assertEqual(foreign_deactivate.status_code, 404)

        self._login(self.trainer_user)
        missing_assignment_delete_csrf = self.client.delete(
            f"/api/v1/trainer/routines/{routine_id}/exercises/{assignment_ids[1]}"
        )
        self.assertEqual(missing_assignment_delete_csrf.status_code, 400)
        removed = self.client.delete(
            f"/api/v1/trainer/routines/{routine_id}/exercises/{assignment_ids[1]}",
            headers=self._json(),
        )
        self.assertEqual(removed.status_code, 200)
        remaining = self.db.execute(
            """
            SELECT orden, series, repeticiones, peso_gramos, descanso_segundos
            FROM rutina_ejercicio WHERE id_rutina_ejercicio = ?
            """,
            (assignment_ids[0],),
        ).fetchone()
        self.assertEqual(tuple(remaining), (1, 4, 8, 25000, 90))
        self.assertIsNotNone(
            self.db.execute(
                "SELECT 1 FROM progresos WHERE id_progreso = ?", (progress_id,)
            ).fetchone()
        )

        missing_delete_csrf = self.client.delete(
            f"/api/v1/trainer/routines/{routine_id}"
        )
        self.assertEqual(missing_delete_csrf.status_code, 400)
        deactivated = self.client.delete(
            f"/api/v1/trainer/routines/{routine_id}", headers=self._json()
        )
        self.assertEqual(deactivated.status_code, 200)
        self.assertEqual(
            self.db.execute(
                "SELECT activa FROM rutinas WHERE id_rutina = ?", (routine_id,)
            ).fetchone()[0],
            0,
        )
        self.assertIsNotNone(
            self.db.execute(
                "SELECT 1 FROM progresos WHERE id_progreso = ?", (progress_id,)
            ).fetchone()
        )

        inactive_edit = self.client.patch(
            f"/api/v1/trainer/routines/{routine_id}/exercises/{assignment_ids[0]}",
            json={"series": 9},
            headers=self._json(),
        )
        self.assertEqual(inactive_edit.status_code, 404)
        inactive_add = self.client.post(
            f"/api/v1/trainer/routines/{routine_id}/exercises",
            json={
                "ejercicio_id": exercise_ids[1],
                "orden": 2,
                "series": 3,
                "repeticiones": 12,
                "descanso_segundos": 60,
            },
            headers=self._json(),
        )
        self.assertEqual(inactive_add.status_code, 404)
        inactive_delete = self.client.delete(
            f"/api/v1/trainer/routines/{routine_id}/exercises/{assignment_ids[0]}",
            headers=self._json(),
        )
        self.assertEqual(inactive_delete.status_code, 404)
        inactive_routine_edit = self.client.patch(
            f"/api/v1/trainer/routines/{routine_id}",
            json={"nombre": "No debe cambiar"},
            headers=self._json(),
        )
        self.assertEqual(inactive_routine_edit.status_code, 404)

        trainer_dashboard = self.client.get("/api/v1/trainer/dashboard")
        dashboard_routine = next(
            item
            for item in trainer_dashboard.json["options"]["routines"]
            if item["id"] == routine_id
        )
        dashboard_assignment = next(
            item
            for item in trainer_dashboard.json["options"]["routine_exercises"]
            if item["id"] == assignment_ids[0]
        )
        self.assertFalse(dashboard_routine["activa"])
        self.assertFalse(dashboard_assignment["rutina_activa"])
        self.assertEqual(dashboard_assignment["ejercicio_id"], exercise_ids[0])

        self._login(self.client_user)
        client_routines = self.client.get("/api/v1/client/routines")
        client_routine = next(
            item for item in client_routines.json["routines"] if item["id"] == routine_id
        )
        self.assertEqual(client_routine["activa"], 0)
        self.assertEqual(client_routine["objetivo"], "Movilidad general")
        self.assertEqual(
            (
                client_routine["ejercicios"][0]["orden"],
                client_routine["ejercicios"][0]["series"],
                client_routine["ejercicios"][0]["repeticiones"],
                client_routine["ejercicios"][0]["peso_gramos"],
                client_routine["ejercicios"][0]["descanso_segundos"],
            ),
            (1, 4, 8, 25000, 90),
        )

        script = ROLE_DASHBOARD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('title: "Editar ejercicio asignado"', script)
        self.assertIn("function trainerRoutineExerciseDelete", script)
        self.assertIn("function trainerRoutineDeactivate", script)
        self.assertIn('rowActions["Ejercicios de rutinas"]', script)
        self.assertIn("filter((item) => item.activa)", script)
        self.assertIn("!assignment.rutina_activa", script)

    def test_manager_is_restricted_to_own_site_and_cannot_reduce_below_enrollment(self):
        self._login(self.manager_user)
        dashboard = self.client.get("/api/v1/manager/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json["site"]["id"], self.site_id)
        conflict = self.client.patch(
            f"/api/v1/manager/classes/{self.future_class}",
            json={"cupo_maximo": 1},
            headers=self._json(),
        )
        self.assertEqual(conflict.status_code, 409)
        updated = self.client.patch(
            f"/api/v1/manager/classes/{self.future_class}",
            json={"cupo_maximo": 4},
            headers=self._json(),
        )
        self.assertEqual(updated.status_code, 200)
        other_site = self.client.patch(
            f"/api/v1/manager/classes/{self.other_class}",
            json={"cupo_maximo": 10},
            headers=self._json(),
        )
        self.assertEqual(other_site.status_code, 404)
        scheduled = self.client.patch(
            f"/api/v1/manager/personnel/{self.trainer_user}",
            json={"activo_en_sede": False},
            headers=self._json(),
        )
        self.assertEqual(scheduled.status_code, 409)
        self.assertEqual(scheduled.json["error"], "trainer_has_scheduled_classes")
        relief_user = self._user("Entrenador", "role-relief-trainer")
        relief_trainer = self.db.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, 'Movilidad')",
            (relief_user,),
        ).lastrowid
        self.db.execute(
            "INSERT INTO entrenador_sede (entrenador_id, sede_id, activo) VALUES (?, ?, 1)",
            (relief_trainer, self.site_id),
        )
        self.db.commit()
        disabled = self.client.patch(
            f"/api/v1/manager/personnel/{relief_user}",
            json={"activo_en_sede": False},
            headers=self._json(),
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(
            self.db.execute(
                "SELECT activo FROM entrenador_sede WHERE entrenador_id = ? AND sede_id = ?",
                (relief_trainer, self.site_id),
            ).fetchone()[0],
            0,
        )

    def test_manager_validates_timezone_availability_and_trainer_overlaps(self):
        self.db.execute(
            """
            INSERT INTO disponibilidad_entrenador
                (entrenador_id, sede_id, dia_semana, hora_inicio, hora_fin)
            VALUES (?, ?, 1, '09:00', '11:00')
            """,
            (self.trainer_id, self.site_id),
        )
        self.db.commit()
        self._login(self.manager_user)
        base = {
            "actividad_id": self.activity_id,
            "entrenador_id": self.trainer_id,
            "cupo_maximo": 8,
        }
        missing_csrf = self.client.post(
            "/api/v1/manager/classes",
            json={
                **base,
                "inicio_utc": "2035-01-08T12:00:00Z",
                "fin_utc": "2035-01-08T13:00:00Z",
            },
        )
        self.assertEqual(missing_csrf.status_code, 400)
        first = self.client.post(
            "/api/v1/manager/classes",
            json={
                **base,
                "inicio_utc": "2035-01-08T12:00:00Z",
                "fin_utc": "2035-01-08T13:00:00Z",
            },
            headers=self._json(),
        )
        self.assertEqual(first.status_code, 201, first.get_data(as_text=True))
        adjacent = self.client.post(
            "/api/v1/manager/classes",
            json={
                **base,
                "inicio_utc": "2035-01-08T13:00:00Z",
                "fin_utc": "2035-01-08T14:00:00Z",
            },
            headers=self._json(),
        )
        self.assertEqual(adjacent.status_code, 201, adjacent.get_data(as_text=True))

        overlap = self.client.post(
            "/api/v1/manager/classes",
            json={
                **base,
                "inicio_utc": "2035-01-08T12:30:00Z",
                "fin_utc": "2035-01-08T13:30:00Z",
            },
            headers=self._json(),
        )
        self.assertEqual(overlap.status_code, 409)
        self.assertEqual(overlap.json["error"], "trainer_schedule_conflict")

        unavailable = self.client.post(
            "/api/v1/manager/classes",
            json={
                **base,
                "inicio_utc": "2035-01-08T14:00:00Z",
                "fin_utc": "2035-01-08T15:00:00Z",
            },
            headers=self._json(),
        )
        self.assertEqual(unavailable.status_code, 409)
        self.assertEqual(unavailable.json["error"], "trainer_unavailable")

        invalid_date = self.client.post(
            "/api/v1/manager/classes",
            json={
                **base,
                "inicio_utc": "2035-02-30T12:00:00Z",
                "fin_utc": "2035-02-30T13:00:00Z",
            },
            headers=self._json(),
        )
        self.assertEqual(invalid_date.status_code, 400)
        self.assertEqual(invalid_date.json["field"], "inicio_utc")

        adjacent_id = adjacent.json["class"]["id"]
        update_overlap = self.client.patch(
            f"/api/v1/manager/classes/{adjacent_id}",
            json={
                "inicio_utc": "2035-01-08T12:30:00Z",
                "fin_utc": "2035-01-08T13:30:00Z",
            },
            headers=self._json(),
        )
        self.assertEqual(update_overlap.status_code, 409)
        self.assertEqual(update_overlap.json["error"], "trainer_schedule_conflict")
        stored = self.db.execute(
            "SELECT inicio_utc, fin_utc FROM clases WHERE id_clase = ?",
            (adjacent_id,),
        ).fetchone()
        self.assertEqual(
            tuple(stored),
            ("2035-01-08T13:00:00Z", "2035-01-08T14:00:00Z"),
        )

        self._login(self.trainer_user)
        forbidden = self.client.post(
            "/api/v1/manager/classes",
            json={
                **base,
                "inicio_utc": "2035-01-15T12:00:00Z",
                "fin_utc": "2035-01-15T13:00:00Z",
            },
            headers=self._json(),
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_manager_toggles_only_own_site_activities(self):
        self._login(self.manager_user)
        missing_csrf = self.client.patch(
            f"/api/v1/manager/activities/{self.activity_id}",
            json={"habilitada": False},
        )
        self.assertEqual(missing_csrf.status_code, 400)

        disabled = self.client.patch(
            f"/api/v1/manager/activities/{self.activity_id}",
            json={"habilitada": False},
            headers=self._json(),
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(
            disabled.json["activity"],
            {"id": self.activity_id, "enabled": False},
        )
        own_state = self.db.execute(
            "SELECT habilitada FROM actividad_sede WHERE actividad_id = ? AND sede_id = ?",
            (self.activity_id, self.site_id),
        ).fetchone()[0]
        other_state = self.db.execute(
            "SELECT habilitada FROM actividad_sede WHERE actividad_id = ? AND sede_id = ?",
            (self.activity_id, self.other_site_id),
        ).fetchone()[0]
        self.assertEqual((own_state, other_state), (0, 1))

        dashboard = self.client.get("/api/v1/manager/dashboard")
        activity = next(
            row
            for section in dashboard.json["sections"]
            if section["title"] == "Actividades"
            for row in section["rows"]
            if row["id"] == self.activity_id
        )
        self.assertIs(activity["habilitada"], False)

        enabled = self.client.patch(
            f"/api/v1/manager/activities/{self.activity_id}",
            json={"habilitada": True},
            headers=self._json(),
        )
        self.assertEqual(enabled.status_code, 200)
        self.assertEqual(
            self.db.execute(
                "SELECT habilitada FROM actividad_sede WHERE actividad_id = ? AND sede_id = ?",
                (self.activity_id, self.site_id),
            ).fetchone()[0],
            1,
        )

        other_activity = self.db.execute(
            "INSERT INTO actividades (nombre) VALUES ('Actividad otra sede')"
        ).lastrowid
        self.db.execute(
            "INSERT INTO actividad_sede (actividad_id, sede_id, habilitada) VALUES (?, ?, 1)",
            (other_activity, self.other_site_id),
        )
        self.db.commit()
        outside_scope = self.client.patch(
            f"/api/v1/manager/activities/{other_activity}",
            json={"habilitada": False},
            headers=self._json(),
        )
        self.assertEqual(outside_scope.status_code, 404)
        self.assertEqual(outside_scope.json["error"], "activity_not_found")

        invalid = self.client.patch(
            f"/api/v1/manager/activities/{self.activity_id}",
            json={"habilitada": "false"},
            headers=self._json(),
        )
        self.assertEqual(invalid.status_code, 400)

        self._login(self.trainer_user)
        forbidden = self.client.patch(
            f"/api/v1/manager/activities/{self.activity_id}",
            json={"habilitada": False},
            headers=self._json(),
        )
        self.assertEqual(forbidden.status_code, 403)

        script = ROLE_DASHBOARD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("function managerActivityToggle", script)
        self.assertIn('`/api/v1/manager/activities/${activity.id}`', script)
        self.assertIn('activity.habilitada ? "Deshabilitar" : "Habilitar"', script)

    def test_manager_dashboard_scopes_operational_details_to_own_site(self):
        own_availability = self.db.execute(
            """
            INSERT INTO disponibilidad_entrenador
                (entrenador_id, sede_id, dia_semana, hora_inicio, hora_fin)
            VALUES (?, ?, 2, '08:00', '10:00')
            """,
            (self.trainer_id, self.site_id),
        ).lastrowid
        foreign_availability = self.db.execute(
            """
            INSERT INTO disponibilidad_entrenador
                (entrenador_id, sede_id, dia_semana, hora_inicio, hora_fin)
            VALUES (?, ?, 3, '09:00', '11:00')
            """,
            (self.trainer_id, self.other_site_id),
        ).lastrowid
        foreign_enrollment = self.db.execute(
            """
            INSERT INTO inscripciones (cliente_id, clase_id, fecha_utc, estado)
            VALUES (?, ?, '2030-01-02T00:00:00Z', 'activa')
            """,
            (self.client_id, self.other_class),
        ).lastrowid
        own_remuneration = self.db.execute(
            """
            INSERT INTO remuneraciones
                (clase_id, importe_unidades_menores, moneda, estado_liquidacion)
            VALUES (?, 150000, 'ARS', 'pendiente')
            """,
            (self.past_class,),
        ).lastrowid
        foreign_remuneration = self.db.execute(
            """
            INSERT INTO remuneraciones
                (clase_id, importe_unidades_menores, moneda, estado_liquidacion)
            VALUES (?, 175000, 'ARS', 'pendiente')
            """,
            (self.other_class,),
        ).lastrowid
        self.db.commit()

        self._login(self.manager_user)
        response = self.client.get("/api/v1/manager/dashboard")
        self.assertEqual(response.status_code, 200)
        sections = {
            section["title"]: section["rows"]
            for section in response.json["sections"]
        }
        self.assertIn(
            own_availability,
            {row["id"] for row in sections["Disponibilidad del personal"]},
        )
        self.assertNotIn(
            foreign_availability,
            {row["id"] for row in sections["Disponibilidad del personal"]},
        )
        self.assertNotIn(
            foreign_enrollment,
            {row["id"] for row in sections["Inscripciones"]},
        )
        remuneration_ids = {row["id"] for row in sections["Remuneraciones"]}
        self.assertIn(own_remuneration, remuneration_ids)
        self.assertNotIn(foreign_remuneration, remuneration_ids)

        trainer = next(
            row for row in sections["Personal de la sede"]
            if row["id"] == self.trainer_user
        )
        self.assertEqual(trainer["especialidad"], "Fuerza")
        self.assertEqual(trainer["email"], "role-trainer@example.test")
        class_option = next(
            item for item in response.json["options"]["classes"]
            if item["id"] == self.future_class
        )
        self.assertEqual(class_option["actividad_id"], self.activity_id)
        self.assertEqual(class_option["entrenador_id"], self.trainer_id)

        script = ROLE_DASHBOARD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("function managerClassEditForm", script)
        self.assertIn("function managerPersonnelForm", script)
        self.assertIn('rowActions["Horarios y cupos"]', script)
        self.assertNotIn('label: "ID de clase"', script)
        self.assertNotIn('label: "ID de usuario Entrenador"', script)
        self.assertIn(
            '["trainer", "manager", "admin", "technician"].includes(role)',
            script,
        )

    def test_admin_crud_reports_and_minimum_permissions_are_safe(self):
        self._login(self.admin_user)
        created_user = self.client.post(
            "/api/v1/admin/users",
            json={
                "nombre": "Nueva",
                "apellido": "Persona",
                "nombre_usuario": "nueva.persona",
                "email": "nueva@example.test",
                "rol_id": self._role_id("Cliente"),
            },
            headers=self._json(),
        )
        self.assertEqual(created_user.status_code, 201)
        created_user_id = created_user.json["user"]["id"]
        self.assertIsNotNone(
            self.db.execute(
                "SELECT id_cliente FROM clientes WHERE usuario_id = ?",
                (created_user_id,),
            ).fetchone()
        )
        incomplete_trainer = self.client.post(
            "/api/v1/admin/users",
            json={
                "nombre": "Entrenador",
                "apellido": "Incompleto",
                "nombre_usuario": "trainer.incomplete",
                "email": "trainer.incomplete@example.test",
                "rol_id": self._role_id("Entrenador"),
            },
            headers=self._json(),
        )
        self.assertEqual(incomplete_trainer.status_code, 400)
        created_trainer = self.client.post(
            "/api/v1/admin/users",
            json={
                "nombre": "Entrenador",
                "apellido": "Completo",
                "nombre_usuario": "trainer.complete",
                "email": "trainer.complete@example.test",
                "rol_id": self._role_id("Entrenador"),
                "especialidad": "Movilidad",
                "sede_id": self.site_id,
            },
            headers=self._json(),
        )
        self.assertEqual(created_trainer.status_code, 201)
        new_trainer_user = created_trainer.json["user"]["id"]
        provisioned = self.db.execute(
            """
            SELECT e.especialidad, es.sede_id, es.activo
            FROM entrenadores e JOIN entrenador_sede es
              ON es.entrenador_id = e.id_entrenador
            WHERE e.usuario_id = ?
            """,
            (new_trainer_user,),
        ).fetchone()
        self.assertEqual(tuple(provisioned), ("Movilidad", self.site_id, 1))
        own_access = self.client.patch(
            f"/api/v1/admin/users/{self.admin_user}",
            json={"activo": False},
            headers=self._json(),
        )
        self.assertEqual(own_access.status_code, 409)
        membership = self.client.post(
            "/api/v1/admin/memberships",
            json={"nombre": "Plan Roles", "precio_unidades_menores": 100000, "moneda": "ARS"},
            headers=self._json(),
        )
        self.assertEqual(membership.status_code, 201, membership.get_data(as_text=True))
        report = self.client.get("/api/v1/admin/reports")
        self.assertEqual(report.status_code, 200)
        self.assertGreaterEqual(report.json["report"]["usuarios_activos"], 8)
        protected = self.client.put(
            f"/api/v1/admin/roles/{self._role_id('Administrador')}/permissions",
            json={"permission_ids": []},
            headers=self._json(),
        )
        self.assertEqual(protected.status_code, 409)
        client_permissions = [
            row[0]
            for row in self.db.execute(
                """
                SELECT p.id_permiso FROM permisos p
                WHERE p.clave IN (?, ?)
                ORDER BY p.clave
                """,
                (CLIENT_VIEWS_PERMISSION, CLIENT_DATA_PERMISSION),
            )
        ]
        required_client = self.client.put(
            f"/api/v1/admin/roles/{self._role_id('Cliente')}/permissions",
            json={"permission_ids": []},
            headers=self._json(),
        )
        self.assertEqual(required_client.status_code, 409)
        cross_role = self.client.put(
            f"/api/v1/admin/roles/{self._role_id('Entrenador')}/permissions",
            json={"permission_ids": client_permissions},
            headers=self._json(),
        )
        self.assertEqual(cross_role.status_code, 409)
        self.assertEqual(cross_role.json["error"], "managed_permission_conflict")
        required_keys = {ADMIN_VIEWS_PERMISSION, ADMIN_DATA_PERMISSION}
        self.assertEqual(
            {
                row[0]
                for row in self.db.execute(
                    """
                    SELECT p.clave FROM rol_permiso rp
                    JOIN permisos p ON p.id_permiso = rp.permiso_id
                    WHERE rp.rol_id = ? AND p.clave IN (?, ?)
                    """,
                    (self._role_id("Administrador"), *required_keys),
                )
            },
            required_keys,
        )

    def test_admin_edits_site_with_csrf_and_frontend_connection(self):
        self._login(self.admin_user)
        rejected = self.client.patch(
            f"/api/v1/admin/sites/{self.site_id}",
            json={"nombre": "Centro sin CSRF"},
        )
        self.assertEqual(rejected.status_code, 400)

        updated_values = {
            "nombre": "Centro Renovado",
            "direccion": "Avenida FitPath 2026",
            "zona_horaria": "America/Argentina/Cordoba",
        }
        updated = self.client.patch(
            f"/api/v1/admin/sites/{self.site_id}",
            json=updated_values,
            headers=self._json(),
        )
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))
        self.assertEqual(updated.json["site"], {"id": self.site_id, **updated_values})
        stored = self.db.execute(
            "SELECT nombre, direccion, zona_horaria FROM sedes WHERE id_sede = ?",
            (self.site_id,),
        ).fetchone()
        self.assertEqual(tuple(stored), tuple(updated_values.values()))

        dashboard = self.client.get("/api/v1/admin/dashboard")
        sites = dashboard.json["options"]["sites"]
        self.assertIn({"id": self.site_id, **updated_values}, sites)

        invalid = self.client.patch(
            f"/api/v1/admin/sites/{self.site_id}",
            json={"direccion": " "},
            headers=self._json(),
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json["field"], "direccion")

        invalid_timezone = self.client.patch(
            f"/api/v1/admin/sites/{self.site_id}",
            json={"zona_horaria": "America/Argentina/Inexistente"},
            headers=self._json(),
        )
        self.assertEqual(invalid_timezone.status_code, 400)
        self.assertEqual(invalid_timezone.json["field"], "zona_horaria")
        self.assertEqual(
            self.db.execute(
                "SELECT zona_horaria FROM sedes WHERE id_sede = ?", (self.site_id,)
            ).fetchone()[0],
            "America/Argentina/Cordoba",
        )

        invalid_new_site = self.client.post(
            "/api/v1/admin/sites",
            json={
                "nombre": "Sede sin zona",
                "direccion": "Calle inválida 1",
                "zona_horaria": "No/Existe",
            },
            headers=self._json(),
        )
        self.assertEqual(invalid_new_site.status_code, 400)
        self.assertEqual(invalid_new_site.json["field"], "zona_horaria")

        self._login(self.trainer_user)
        forbidden = self.client.patch(
            f"/api/v1/admin/sites/{self.site_id}",
            json={"nombre": "Cambio no autorizado"},
            headers=self._json(),
        )
        self.assertEqual(forbidden.status_code, 403)

        script = ROLE_DASHBOARD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('title: "Editar sede"', script)
        self.assertIn('`/api/v1/admin/sites/${raw.site_id}`', script)
        self.assertIn('label: "Editar"', script)
        self.assertIn("registerSiteEditor", script)

    def test_admin_uses_real_selectors_and_supervises_maintenance_history(self):
        ticket_id = self.db.execute(
            """
            INSERT INTO tickets_mantenimiento
                (maquina_id, tecnico_id, fecha_generacion_utc, descripcion, estado)
            VALUES (?, ?, '2026-01-10T10:00:00Z', 'Revisión administrativa', 'abierto')
            """,
            (self.machine_id, self.technician_id),
        ).lastrowid
        history_id = self.db.execute(
            """
            INSERT INTO historial_mantenimiento
                (maquina_id, ticket_id, tecnico_id, fecha_utc,
                 estado_anterior, estado_nuevo, descripcion)
            VALUES (?, ?, ?, '2026-01-10T10:05:00Z',
                    'operativa', 'en_reparacion', 'Diagnóstico inicial')
            """,
            (self.machine_id, ticket_id, self.technician_id),
        ).lastrowid
        self.db.commit()
        self._login(self.admin_user)

        missing_csrf = self.client.patch(
            f"/api/v1/admin/activities/{self.activity_id}",
            json={"nombre": "Actividad sin CSRF"},
        )
        self.assertEqual(missing_csrf.status_code, 400)
        renamed = self.client.patch(
            f"/api/v1/admin/activities/{self.activity_id}",
            json={"nombre": "Funcional Administrado"},
            headers=self._json(),
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(
            self.db.execute(
                "SELECT nombre FROM actividades WHERE id_actividad = ?",
                (self.activity_id,),
            ).fetchone()[0],
            "Funcional Administrado",
        )

        dashboard = self.client.get("/api/v1/admin/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        sections = {
            section["title"]: section["rows"]
            for section in dashboard.json["sections"]
        }
        self.assertIn(self.machine_id, {row["id"] for row in sections["Máquinas"]})
        self.assertIn(ticket_id, {row["id"] for row in sections["Tickets de mantenimiento"]})
        self.assertIn(
            history_id,
            {row["id"] for row in sections["Historial de mantenimiento"]},
        )
        trainer = next(
            item for item in dashboard.json["options"]["users"]
            if item["id"] == self.trainer_user
        )
        self.assertEqual(trainer["especialidad"], "Fuerza")
        self.assertEqual(trainer["sede_id"], self.site_id)
        self.assertIs(trainer["activo"], True)
        admin_role = next(
            item for item in dashboard.json["options"]["roles"]
            if item["nombre"] == "Administrador"
        )
        self.assertTrue(admin_role["permission_ids"])
        self.assertIn("administrador.datos", admin_role["permissions"])

        script = ROLE_DASHBOARD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("function userAccessForm", script)
        self.assertIn("function activityEditForm", script)
        self.assertIn("function rolePermissionsForm", script)
        self.assertIn("registerUserEditor", script)
        self.assertIn("registerActivityEditor", script)
        self.assertNotIn('label: "ID de usuario"', script)
        self.assertNotIn('label: "IDs de permisos"', script)
        self.assertIn(
            '["trainer", "manager", "admin", "technician"].includes(role)',
            script,
        )

    def test_admin_creates_machine_and_technician_sees_it_only_at_own_site(self):
        self._login(self.admin_user)
        created = self.client.post(
            "/api/v1/admin/machines",
            json={
                "sede_id": self.site_id,
                "tipo": "Remadora",
                "estado": "en_reparacion",
            },
            headers=self._json(),
        )
        self.assertEqual(created.status_code, 201)
        machine = created.json["machine"]
        self.assertEqual(machine["sede_id"], self.site_id)
        self.assertEqual(machine["sede"], "Centro Roles")
        self.assertEqual(machine["tipo"], "Remadora")
        self.assertEqual(machine["estado"], "en_reparacion")
        self.assertEqual(
            tuple(self.db.execute(
                "SELECT sede_id, tipo, estado FROM maquinas WHERE id_maquina = ?",
                (machine["id"],),
            ).fetchone()),
            (self.site_id, "Remadora", "en_reparacion"),
        )
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM historial_mantenimiento WHERE maquina_id = ?",
                (machine["id"],),
            ).fetchone()[0],
            0,
        )

        admin_dashboard = self.client.get("/api/v1/admin/dashboard")
        admin_machines = next(
            section["rows"] for section in admin_dashboard.json["sections"]
            if section["title"] == "Máquinas"
        )
        self.assertIn(machine["id"], {item["id"] for item in admin_machines})

        self._login(self.technician_user)
        technician_dashboard = self.client.get("/api/v1/technician/dashboard")
        self.assertIn(
            machine["id"],
            {item["id"] for item in technician_dashboard.json["options"]["machines"]},
        )
        self._login(self.other_technician_user)
        other_dashboard = self.client.get("/api/v1/technician/dashboard")
        self.assertNotIn(
            machine["id"],
            {item["id"] for item in other_dashboard.json["options"]["machines"]},
        )

        script = ROLE_DASHBOARD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('title: "Registrar máquina"', script)
        self.assertIn('path: "/api/v1/admin/machines"', script)
        self.assertIn('name: "sede_id", label: "Sede", options: sites', script)

    def test_admin_machine_creation_validates_csrf_site_state_role_and_permission(self):
        payload = {"sede_id": self.site_id, "tipo": "Elíptica", "estado": "operativa"}
        baseline = self.db.execute("SELECT count(*) FROM maquinas").fetchone()[0]
        self.assertEqual(
            self.client.post("/api/v1/admin/machines", json=payload).status_code,
            401,
        )
        self._login(self.technician_user)
        self.assertEqual(
            self.client.post(
                "/api/v1/admin/machines", json=payload, headers=self._json()
            ).status_code,
            403,
        )
        self._login(self.admin_user)
        self.assertEqual(
            self.client.post("/api/v1/admin/machines", json=payload).status_code,
            400,
        )
        missing_site = self.client.post(
            "/api/v1/admin/machines",
            json={**payload, "sede_id": 999999},
            headers=self._json(),
        )
        self.assertEqual(missing_site.status_code, 404)
        self.assertEqual(missing_site.json["error"], "site_not_found")
        invalid_state = self.client.post(
            "/api/v1/admin/machines",
            json={**payload, "estado": "desconocida"},
            headers=self._json(),
        )
        self.assertEqual(invalid_state.status_code, 400)
        self.assertEqual(invalid_state.json["field"], "estado")
        invalid_type = self.client.post(
            "/api/v1/admin/machines",
            json={**payload, "tipo": "   "},
            headers=self._json(),
        )
        self.assertEqual(invalid_type.status_code, 400)
        self.assertEqual(invalid_type.json["field"], "tipo")
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM maquinas").fetchone()[0],
            baseline,
        )

        self.db.execute(
            """
            DELETE FROM rol_permiso
            WHERE rol_id = (SELECT id_rol FROM roles WHERE nombre = 'Administrador')
              AND permiso_id = (SELECT id_permiso FROM permisos WHERE clave = ?)
            """,
            (ADMIN_DATA_PERMISSION,),
        )
        self.db.commit()
        self.assertEqual(
            self.client.post(
                "/api/v1/admin/machines", json=payload, headers=self._json()
            ).status_code,
            403,
        )

    def test_admin_can_register_same_machine_type_as_distinct_units(self):
        self._login(self.admin_user)
        payload = {"sede_id": self.site_id, "tipo": "Cinta", "estado": "operativa"}
        first = self.client.post(
            "/api/v1/admin/machines", json=payload, headers=self._json()
        )
        second = self.client.post(
            "/api/v1/admin/machines", json=payload, headers=self._json()
        )
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        self.assertNotEqual(first.json["machine"]["id"], second.json["machine"]["id"])
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM maquinas WHERE sede_id = ? AND tipo = 'Cinta'",
                (self.site_id,),
            ).fetchone()[0],
            3,
        )

    def test_admin_manages_memberships_and_benefits_without_rewriting_debts(self):
        self._login(self.admin_user)
        missing_csrf = self.client.post(
            "/api/v1/admin/benefits",
            json={"nombre": "Sin CSRF"},
        )
        self.assertEqual(missing_csrf.status_code, 400)

        membership = self.client.post(
            "/api/v1/admin/memberships",
            json={
                "nombre": "Plan Integral",
                "precio_unidades_menores": 250000,
                "moneda": "ARS",
                "descripcion": "Plan de prueba focalizada.",
            },
            headers=self._json(),
        )
        self.assertEqual(membership.status_code, 201)
        membership_id = membership.json["membership"]["id"]

        benefit = self.client.post(
            "/api/v1/admin/benefits",
            json={"nombre": "Beneficio configurable", "descripcion": "Sin regla comercial."},
            headers=self._json(),
        )
        self.assertEqual(benefit.status_code, 201)
        benefit_id = benefit.json["benefit"]["id"]
        duplicate = self.client.post(
            "/api/v1/admin/benefits",
            json={"nombre": "Beneficio configurable"},
            headers=self._json(),
        )
        self.assertEqual(duplicate.status_code, 409)
        edited_benefit = self.client.patch(
            f"/api/v1/admin/benefits/{benefit_id}",
            json={"nombre": "Beneficio actualizado", "descripcion": None},
            headers=self._json(),
        )
        self.assertEqual(edited_benefit.status_code, 200)

        subscription_id = self.db.execute(
            """
            INSERT INTO cliente_membresia
                (cliente_id, membresia_id, fecha_inicio, fecha_fin, estado)
            VALUES (?, ?, '2026-01-01', NULL, 'vencida')
            """,
            (self.client_id, membership_id),
        ).lastrowid
        debt_id = self.db.execute(
            """
            INSERT INTO deudas
                (cliente_id, cliente_membresia_id, concepto,
                 importe_unidades_menores, moneda, vence_el)
            VALUES (?, ?, 'Obligación histórica', 250000, 'ARS', '2026-01-01')
            """,
            (self.client_id, subscription_id),
        ).lastrowid
        self.db.commit()

        edited_membership = self.client.patch(
            f"/api/v1/admin/memberships/{membership_id}",
            json={
                "nombre": "Plan Integral Actualizado",
                "precio_unidades_menores": 300000,
                "moneda": "ARS",
                "descripcion": None,
                "activa": True,
            },
            headers=self._json(),
        )
        self.assertEqual(edited_membership.status_code, 200)
        self.assertEqual(
            self.db.execute(
                "SELECT importe_unidades_menores FROM deudas WHERE id_deuda = ?",
                (debt_id,),
            ).fetchone()[0],
            250000,
        )

        assigned = self.client.put(
            f"/api/v1/admin/memberships/{membership_id}/benefits",
            json={"benefit_ids": [benefit_id]},
            headers=self._json(),
        )
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.json["membership"]["benefit_ids"], [benefit_id])
        missing_benefit = self.client.put(
            f"/api/v1/admin/memberships/{membership_id}/benefits",
            json={"benefit_ids": [999999]},
            headers=self._json(),
        )
        self.assertEqual(missing_benefit.status_code, 404)
        self.assertEqual(
            self.db.execute(
                "SELECT beneficio_id FROM membresia_beneficio WHERE membresia_id = ?",
                (membership_id,),
            ).fetchone()[0],
            benefit_id,
        )
        duplicate_ids = self.client.put(
            f"/api/v1/admin/memberships/{membership_id}/benefits",
            json={"benefit_ids": [benefit_id, benefit_id]},
            headers=self._json(),
        )
        self.assertEqual(duplicate_ids.status_code, 400)

        dashboard = self.client.get("/api/v1/admin/dashboard")
        membership_option = next(
            item
            for item in dashboard.json["options"]["memberships"]
            if item["id"] == membership_id
        )
        self.assertEqual(membership_option["beneficio_ids"], [benefit_id])
        self.assertEqual(membership_option["beneficios"], "Beneficio actualizado")

        self._login(self.client_user)
        client_catalog = self.client.get("/api/v1/client/memberships")
        client_membership = next(
            item
            for item in client_catalog.json["memberships"]
            if item["id"] == membership_id
        )
        self.assertEqual(client_membership["beneficios"], "Beneficio actualizado")

        self._login(self.admin_user)
        removed = self.client.put(
            f"/api/v1/admin/memberships/{membership_id}/benefits",
            json={"benefit_ids": []},
            headers=self._json(),
        )
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM membresia_beneficio WHERE membresia_id = ?",
                (membership_id,),
            ).fetchone()[0],
            0,
        )

        self._login(self.trainer_user)
        forbidden = self.client.post(
            "/api/v1/admin/benefits",
            json={"nombre": "No autorizado"},
            headers=self._json(),
        )
        self.assertEqual(forbidden.status_code, 403)
        forbidden_assignment = self.client.put(
            f"/api/v1/admin/memberships/{membership_id}/benefits",
            json={"benefit_ids": [benefit_id]},
            headers=self._json(),
        )
        self.assertEqual(forbidden_assignment.status_code, 403)

        script = ROLE_DASHBOARD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('title: "Editar membresía"', script)
        self.assertIn('title: "Crear beneficio"', script)
        self.assertIn('title: "Configurar beneficios"', script)
        self.assertIn('`/api/v1/admin/memberships/${raw.membership_id}/benefits`', script)

    def test_technician_ticket_machine_state_and_history_are_site_scoped(self):
        self._login(self.technician_user)
        missing_csrf = self.client.post(
            "/api/v1/technician/tickets",
            json={"maquina_id": self.machine_id, "descripcion": "Sin CSRF"},
        )
        self.assertEqual(missing_csrf.status_code, 400)
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM tickets_mantenimiento").fetchone()[0],
            0,
        )
        denied = self.client.post(
            "/api/v1/technician/tickets",
            json={"maquina_id": self.other_machine_id, "descripcion": "No autorizada"},
            headers=self._json(),
        )
        self.assertEqual(denied.status_code, 404)
        ticket = self.client.post(
            "/api/v1/technician/tickets",
            json={"maquina_id": self.machine_id, "descripcion": "Ruido anormal"},
            headers=self._json(),
        )
        self.assertEqual(ticket.status_code, 201)
        ticket_id = ticket.json["ticket"]["id"]
        changed = self.client.patch(
            f"/api/v1/technician/machines/{self.machine_id}",
            json={"estado": "en_reparacion", "ticket_id": ticket_id, "descripcion": "Retirada de servicio"},
            headers=self._json(),
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(
            self.db.execute(
                "SELECT estado FROM maquinas WHERE id_maquina = ?", (self.machine_id,)
            ).fetchone()[0],
            "en_reparacion",
        )
        history = self.db.execute(
            "SELECT estado_anterior, estado_nuevo, ticket_id FROM historial_mantenimiento WHERE maquina_id = ?",
            (self.machine_id,),
        ).fetchone()
        self.assertEqual(tuple(history), ("operativa", "en_reparacion", ticket_id))
        resolved = self.client.patch(
            f"/api/v1/technician/tickets/{ticket_id}",
            json={"estado": "resuelto"},
            headers=self._json(),
        )
        self.assertEqual(resolved.status_code, 200)

        unchanged = self.client.patch(
            f"/api/v1/technician/machines/{self.machine_id}",
            json={"estado": "en_reparacion"},
            headers=self._json(),
        )
        self.assertEqual(unchanged.status_code, 409)
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM historial_mantenimiento WHERE maquina_id = ?",
                (self.machine_id,),
            ).fetchone()[0],
            1,
        )
        destructive = self.client.delete(
            f"/api/v1/technician/tickets/{ticket_id}",
            headers=self._json(),
        )
        self.assertEqual(destructive.status_code, 405)
        self.assertIsNotNone(
            self.db.execute(
                "SELECT 1 FROM tickets_mantenimiento WHERE id_ticket = ?", (ticket_id,)
            ).fetchone()
        )

        dashboard = self.client.get("/api/v1/technician/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json["site"]["id"], self.site_id)
        history_rows = next(
            section["rows"]
            for section in dashboard.json["sections"]
            if section["title"] == "Historial de mantenimiento"
        )
        self.assertEqual(len(history_rows), 1)

        self._login(self.manager_user)
        forbidden = self.client.post(
            "/api/v1/technician/tickets",
            json={"maquina_id": self.machine_id, "descripcion": "Rol incorrecto"},
            headers=self._json(),
        )
        self.assertEqual(forbidden.status_code, 403)

        script = ROLE_DASHBOARD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("function technicianTicketForm", script)
        self.assertIn("function technicianMachineForm", script)
        self.assertIn('rowActions["Máquinas de la sede"]', script)
        self.assertIn('rowActions["Incidencias asignadas"]', script)
        self.assertIn("candidate.maquina_id === item.id", script)
        self.assertIn(
            '["trainer", "manager", "admin", "technician"].includes(role)',
            script,
        )

    def test_technician_assignment_preserves_records_and_hides_other_site(self):
        self._login(self.technician_user)
        ticket = self.client.post(
            "/api/v1/technician/tickets",
            json={"maquina_id": self.machine_id, "descripcion": "Registro histórico"},
            headers=self._json(),
        )
        self.assertEqual(ticket.status_code, 201)
        ticket_id = ticket.json["ticket"]["id"]
        foreign_ticket = self.db.execute(
            """
            INSERT INTO tickets_mantenimiento
                (maquina_id, tecnico_id, fecha_generacion_utc, descripcion, estado)
            VALUES (?, ?, '2026-02-01T10:00:00Z', 'Otra sede', 'abierto')
            """,
            (self.other_machine_id, self.other_technician_id),
        ).lastrowid
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                "UPDATE tecnicos_mantenimiento SET sede_id = ? WHERE id_tecnico = ?",
                (self.other_site_id, self.technician_id),
            )
        self.db.rollback()

        dashboard = self.client.get("/api/v1/technician/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json["site"]["id"], self.site_id)
        self.assertEqual(
            {item["id"] for item in dashboard.json["options"]["machines"]},
            {self.machine_id},
        )
        self.assertEqual(
            {item["id"] for item in dashboard.json["options"]["tickets"]},
            {ticket_id},
        )

        foreign_ticket_update = self.client.patch(
            f"/api/v1/technician/tickets/{foreign_ticket}",
            json={"estado": "resuelto"},
            headers=self._json(),
        )
        self.assertEqual(foreign_ticket_update.status_code, 404)
        foreign_machine = self.client.patch(
            f"/api/v1/technician/machines/{self.other_machine_id}",
            json={"estado": "en_reparacion"},
            headers=self._json(),
        )
        self.assertEqual(foreign_machine.status_code, 404)
        self.assertEqual(
            self.db.execute(
                "SELECT sede_id FROM tecnicos_mantenimiento WHERE id_tecnico = ?",
                (self.technician_id,),
            ).fetchone()[0],
            self.site_id,
        )


if __name__ == "__main__":
    unittest.main()
