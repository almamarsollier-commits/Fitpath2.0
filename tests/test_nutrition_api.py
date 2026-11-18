"""Pruebas focalizadas de consulta segura de planes de alimentación."""

import tempfile
import unittest
from pathlib import Path

from backend.fitpath import create_app
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.seeds import seed_initial_permissions, seed_initial_roles


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPOSITORY_ROOT / "backend" / "fitpath" / "migrations"
CLIENT_DATA_SCRIPT = REPOSITORY_ROOT / "statics" / "js" / "modules" / "client-data.js"
CLIENT_SHELL_SCRIPT = REPOSITORY_ROOT / "statics" / "js" / "modules" / "cliente-shell.js"
ROLE_DASHBOARD_SCRIPT = REPOSITORY_ROOT / "statics" / "js" / "modules" / "role-dashboard.js"


class NutritionApiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database_path = Path(temporary.name) / "nutrition-api.sqlite3"
        self.app = create_app(
            "testing",
            {
                "DATABASE": str(self.database_path),
                "MIGRATIONS_DIR": str(MIGRATIONS_DIR),
                "SECRET_KEY": "nutrition-api-test-secret",
            },
        )
        self.client = self.app.test_client()
        self.db = connect_database(self.database_path)
        self.addCleanup(self.db.close)
        self.assertEqual(apply_migrations(self.db, MIGRATIONS_DIR), tuple(range(1, 15)))
        seed_initial_roles(self.db)
        seed_initial_permissions(self.db)

        self.client_user_id = self._user("Cliente", "nutrition-client")
        self.other_user_id = self._user("Cliente", "nutrition-other")
        self.trainer_user_id = self._user("Entrenador", "nutrition-trainer")
        self.admin_user_id = self._user("Administrador", "nutrition-admin")
        self.client_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (self.client_user_id,)
        ).lastrowid
        self.other_client_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (self.other_user_id,)
        ).lastrowid
        self.trainer_id = self.db.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, 'Fuerza')",
            (self.trainer_user_id,),
        ).lastrowid
        site_id = self.db.execute(
            """
            INSERT INTO sedes (nombre, direccion, zona_horaria)
            VALUES ('Sede nutricion', 'Calle 10', 'America/Argentina/Buenos_Aires')
            """
        ).lastrowid
        self.db.execute(
            "INSERT INTO entrenador_sede (entrenador_id, sede_id, activo) VALUES (?, ?, 1)",
            (self.trainer_id, site_id),
        )
        activity_id = self.db.execute(
            "INSERT INTO actividades (nombre) VALUES ('Actividad nutricion')"
        ).lastrowid
        self.db.execute(
            "INSERT INTO actividad_sede (actividad_id, sede_id, habilitada) VALUES (?, ?, 1)",
            (activity_id, site_id),
        )
        class_id = self.db.execute(
            """
            INSERT INTO clases
                (actividad_id, sede_id, entrenador_id, inicio_utc,
                 fin_utc, cupo_maximo, estado)
            VALUES (?, ?, ?, '2035-01-10T18:00:00Z',
                    '2035-01-10T19:00:00Z', 10, 'programada')
            """,
            (activity_id, site_id, self.trainer_id),
        ).lastrowid
        self.db.execute(
            """
            INSERT INTO inscripciones (cliente_id, clase_id, fecha_utc, estado)
            VALUES (?, ?, '2030-01-01T00:00:00Z', 'activa')
            """,
            (self.client_id, class_id),
        )
        objective_type_id = self.db.execute(
            "INSERT INTO tipos_objetivo (nombre) VALUES ('Habitos saludables')"
        ).lastrowid
        self.objective_id = self.db.execute(
            """
            INSERT INTO objetivos (tipo_objetivo_id, nombre)
            VALUES (?, 'Mejorar habitos')
            """,
            (objective_type_id,),
        ).lastrowid
        self.db.executemany(
            "INSERT INTO cliente_objetivo (cliente_id, objetivo_id) VALUES (?, ?)",
            (
                (self.client_id, self.objective_id),
                (self.other_client_id, self.objective_id),
            ),
        )
        self.plan_id = self._plan(self.client_id, "Plan propio")
        self.other_plan_id = self._plan(self.other_client_id, "Plan ajeno")
        self.db.commit()

    def _role(self, name):
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
            (role, username, f"{username}@example.test", self._role(role)),
        ).lastrowid

    def _plan(self, client_id, name):
        return self.db.execute(
            """
            INSERT INTO planes_alimentacion
                (cliente_id, objetivo_id, nombre, descripcion, indicaciones,
                 fecha_creacion_utc, fecha_actualizacion_utc)
            VALUES (?, ?, ?, 'Descripcion persistida', 'Indicacion persistida',
                    '2030-01-01T00:00:00Z', '2030-01-02T00:00:00Z')
            """,
            (client_id, self.objective_id, name),
        ).lastrowid

    def _login(self, user_id):
        with self.client.session_transaction() as session:
            session["fitpath_user_id"] = user_id
            session["csrf_token"] = "nutrition-api-csrf"

    def _plans_snapshot(self):
        return [
            tuple(row)
            for row in self.db.execute(
                "SELECT * FROM planes_alimentacion ORDER BY id_plan_alimentacion"
            ).fetchall()
        ]

    def test_client_lists_and_reads_only_own_plans_without_mutating_history(self):
        before = self._plans_snapshot()
        self._login(self.client_user_id)

        response = self.client.get("/api/v1/client/nutrition-plans")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        plans = response.get_json()["nutrition_plans"]
        self.assertEqual([plan["id"] for plan in plans], [self.plan_id])
        self.assertEqual(plans[0]["objetivo"]["id"], self.objective_id)
        self.assertEqual(plans[0]["objetivo"]["tipo"], "Habitos saludables")

        detail = self.client.get(f"/api/v1/client/nutrition-plans/{self.plan_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["nutrition_plan"]["nombre"], "Plan propio")
        forbidden = self.client.get(
            f"/api/v1/client/nutrition-plans/{self.other_plan_id}"
        )
        self.assertEqual(forbidden.status_code, 404)
        self.assertEqual(before, self._plans_snapshot())

    def test_trainer_reads_only_plans_of_functionally_linked_clients(self):
        self._login(self.trainer_user_id)

        response = self.client.get(
            f"/api/v1/trainer/clients/{self.client_id}/nutrition-plans"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [plan["id"] for plan in response.get_json()["nutrition_plans"]],
            [self.plan_id],
        )
        detail = self.client.get(
            f"/api/v1/trainer/clients/{self.client_id}/nutrition-plans/{self.plan_id}"
        )
        self.assertEqual(detail.status_code, 200)
        unlinked = self.client.get(
            f"/api/v1/trainer/clients/{self.other_client_id}/nutrition-plans"
        )
        self.assertEqual(unlinked.status_code, 403)
        self.assertEqual(unlinked.get_json()["error"], "student_not_authorized")
        foreign_plan = self.client.get(
            f"/api/v1/trainer/clients/{self.client_id}/nutrition-plans/{self.other_plan_id}"
        )
        self.assertEqual(foreign_plan.status_code, 404)

    def test_endpoints_require_authentication_role_and_do_not_offer_writes(self):
        self.assertEqual(
            self.client.get("/api/v1/client/nutrition-plans").status_code, 401
        )
        self._login(self.admin_user_id)
        self.assertEqual(
            self.client.get("/api/v1/client/nutrition-plans").status_code, 403
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/trainer/clients/{self.client_id}/nutrition-plans"
            ).status_code,
            403,
        )
        self._login(self.client_user_id)
        self.assertEqual(
            self.client.post(
                "/api/v1/client/nutrition-plans",
                json={"nombre": "Sin regla aprobada"},
                headers={"X-CSRF-Token": "nutrition-api-csrf"},
            ).status_code,
            405,
        )

    def test_nutrition_interfaces_use_protected_views_and_read_only_endpoints(self):
        paths = (
            "/templates/cliente/alimentacion/index.html",
            "/templates/cliente/alimentacion/detalle.html?plan=1",
        )
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 302)

        self._login(self.client_user_id)
        for path in paths:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("private", response.headers["Cache-Control"])
            self.assertIn("no-store", response.headers["Cache-Control"])
            response.close()

        self._login(self.trainer_user_id)
        trainer_page = self.client.get("/auth/entrenador")
        self.assertEqual(trainer_page.status_code, 200)
        self.assertIn(b"role-dashboard.js", trainer_page.data)
        trainer_page.close()
        denied_client_view = self.client.get(paths[0])
        self.assertEqual(denied_client_view.status_code, 403)
        denied_client_view.close()

        client_data = CLIENT_DATA_SCRIPT.read_text(encoding="utf-8")
        client_shell = CLIENT_SHELL_SCRIPT.read_text(encoding="utf-8")
        trainer_dashboard = ROLE_DASHBOARD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('api("/api/v1/client/nutrition-plans")', client_data)
        self.assertIn('positiveQueryParameter("plan")', client_data)
        self.assertIn("nutritionDetailHref(plan.id)", client_data)
        self.assertIn('label: "Mi alimentación"', client_shell)
        self.assertIn("function trainerNutritionViewer", trainer_dashboard)
        self.assertIn(
            "`/api/v1/trainer/clients/${select.value}/nutrition-plans`",
            trainer_dashboard,
        )
        self.assertIn("Información asignada de solo lectura", trainer_dashboard)


if __name__ == "__main__":
    unittest.main()
