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

    def test_technician_ticket_machine_state_and_history_are_site_scoped(self):
        self._login(self.technician_user)
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


if __name__ == "__main__":
    unittest.main()
