import tempfile
import unittest
from pathlib import Path

from backend.fitpath import create_app
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.seeds import (
    seed_initial_currencies,
    seed_initial_permissions,
    seed_initial_roles,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PAYMENTS_SCRIPT = REPOSITORY_ROOT / "statics" / "js" / "modules" / "payments.js"
MEMBERSHIP_VIEW = REPOSITORY_ROOT / "templates" / "cliente" / "perfil" / "membresia.html"


class ClientMembershipTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        database = Path(temporary.name) / "memberships.sqlite3"
        self.app = create_app(
            "testing",
            {"DATABASE": str(database), "SECRET_KEY": "membership-test-secret"},
        )
        self.client = self.app.test_client()
        self.db = connect_database(database)
        self.addCleanup(self.db.close)
        apply_migrations(self.db, self.app.config["MIGRATIONS_DIR"])
        seed_initial_roles(self.db)
        seed_initial_permissions(self.db)
        seed_initial_currencies(self.db)
        role_id = self.db.execute(
            "SELECT id_rol FROM roles WHERE nombre = 'Cliente'"
        ).fetchone()[0]
        user_id = self.db.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES ('Membresía', 'Prueba', 'membership-client',
                    'membership-client@example.test', ?, 1)
            """,
            (role_id,),
        ).lastrowid
        self.client_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (user_id,)
        ).lastrowid
        self.paid_id = self.db.execute(
            """
            INSERT INTO membresias
                (nombre, precio_unidades_menores, moneda, descripcion, activa)
            VALUES ('Plan pago', 250000, 'ARS', 'Plan de prueba', 1)
            """
        ).lastrowid
        self.free_id = self.db.execute(
            """
            INSERT INTO membresias
                (nombre, precio_unidades_menores, moneda, descripcion, activa)
            VALUES ('Plan gratuito', 0, 'ARS', 'Plan sin deuda', 1)
            """
        ).lastrowid
        self.db.commit()
        with self.client.session_transaction() as session:
            session["fitpath_user_id"] = user_id
            session["csrf_token"] = "membership-csrf"

    def test_catalog_selection_obligation_and_activation_rules(self):
        catalog = self.client.get("/api/v1/client/memberships")
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual({item["id"] for item in catalog.json["memberships"]}, {self.paid_id, self.free_id})

        missing_csrf = self.client.post(
            f"/api/v1/client/memberships/{self.paid_id}/select"
        )
        self.assertEqual(missing_csrf.status_code, 400)
        selected = self.client.post(
            f"/api/v1/client/memberships/{self.paid_id}/select",
            headers={"X-CSRF-Token": "membership-csrf"},
        )
        self.assertEqual(selected.status_code, 201)
        self.assertEqual(selected.json["subscription"]["status"], "vencida")
        debt_id = selected.json["subscription"]["debt_id"]
        debt = self.db.execute(
            "SELECT importe_unidades_menores, estado FROM deudas WHERE id_deuda = ?",
            (debt_id,),
        ).fetchone()
        self.assertEqual(tuple(debt), (250000, "pendiente"))
        duplicate = self.client.post(
            f"/api/v1/client/memberships/{self.paid_id}/select",
            headers={"X-CSRF-Token": "membership-csrf"},
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json["debt_id"], debt_id)

        free = self.client.post(
            f"/api/v1/client/memberships/{self.free_id}/select",
            headers={"X-CSRF-Token": "membership-csrf"},
        )
        self.assertEqual(free.status_code, 201)
        self.assertEqual(free.json["subscription"]["status"], "activa")
        self.assertIsNone(free.json["subscription"]["debt_id"])
        blocked = self.client.post(
            f"/api/v1/client/memberships/{self.paid_id}/select",
            headers={"X-CSRF-Token": "membership-csrf"},
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json["error"], "active_membership_exists")

        history = self.client.get("/api/v1/client/memberships")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json["active"]["membresia_id"], self.free_id)
        self.assertEqual(
            [item["estado"] for item in history.json["subscriptions"]],
            ["activa", "vencida"],
        )
        self.assertEqual(
            {item["membresia_id"] for item in history.json["subscriptions"]},
            {self.paid_id, self.free_id},
        )
        debt_after_history = self.db.execute(
            "SELECT importe_unidades_menores, estado FROM deudas WHERE id_deuda = ?",
            (debt_id,),
        ).fetchone()
        self.assertEqual(tuple(debt_after_history), (250000, "pendiente"))

        with self.client.session_transaction() as session:
            session.clear()
        unauthorized = self.client.get("/api/v1/client/memberships")
        self.assertEqual(unauthorized.status_code, 401)

    def test_membership_view_connects_catalog_history_debts_and_test_checkout(self):
        script = PAYMENTS_SCRIPT.read_text(encoding="utf-8")
        view = MEMBERSHIP_VIEW.read_text(encoding="utf-8")
        for marker in (
            "data-membership-catalog",
            "data-membership-history",
            "data-payment-debts",
            "data-payment-history",
            "data-payment-status",
        ):
            self.assertIn(marker, view)
        self.assertIn('fetch("/api/v1/client/payments"', script)
        self.assertIn('fetch("/api/v1/client/memberships"', script)
        self.assertIn('fetch("/api/v1/client/payment-intents"', script)
        self.assertIn('"X-CSRF-Token": csrfToken', script)
        self.assertIn("button.disabled = !checkoutAvailable", script)


if __name__ == "__main__":
    unittest.main()
