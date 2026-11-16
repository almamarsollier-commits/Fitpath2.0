"""Pruebas locales de Checkout Pro, sin credenciales ni comunicación externa."""

import hashlib
import hmac
import tempfile
import time
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.fitpath import create_app
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import apply_migrations
from backend.fitpath.seeds import (
    seed_initial_currencies,
    seed_initial_permissions,
    seed_initial_roles,
)
from backend.fitpath.services.mercado_pago import (
    MercadoPagoConfigurationError,
    MercadoPagoSettings,
    create_mercado_pago_client,
)
from backend.fitpath.services.payment_intents import (
    WebhookSignatureError,
    verify_webhook_signature,
)


TEST_CONFIG = {
    "MERCADOPAGO_ACCESS_TOKEN": "APP_" + "USR-local-test-token-never-real",
    "MERCADOPAGO_WEBHOOK_SECRET": "local-webhook-secret-never-real",
    "MERCADOPAGO_PUBLIC_BASE_URL": "https://fitpath.example.test",
    "MERCADOPAGO_CREDENTIAL_SCOPE": "test",
    "MERCADOPAGO_TIMEOUT_SECONDS": "5",
    "MERCADOPAGO_WEBHOOK_TOLERANCE_SECONDS": "300",
}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeRequestsSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return FakeResponse(self.payload)


class FakeMercadoPago:
    def __init__(self):
        self.settings = SimpleNamespace(
            public_base_url=TEST_CONFIG["MERCADOPAGO_PUBLIC_BASE_URL"]
        )
        self.preferences = []
        self.payments = {}

    def create_preference(self, payload, idempotency_key):
        self.preferences.append((payload, idempotency_key))
        number = len(self.preferences)
        return {
            "preference_id": f"test-preference-{number}",
            "checkout_url": f"https://sandbox.mercadopago.com.ar/checkout/{number}",
        }

    def get_payment(self, payment_id):
        return self.payments[str(payment_id)]


class MercadoPagoClientTests(unittest.TestCase):
    def test_configuration_requires_explicit_test_scope_and_https(self):
        for key, value in (
            ("MERCADOPAGO_CREDENTIAL_SCOPE", None),
            ("MERCADOPAGO_CREDENTIAL_SCOPE", "production"),
            ("MERCADOPAGO_PUBLIC_BASE_URL", "http://localhost:5000"),
            ("MERCADOPAGO_ACCESS_TOKEN", "short"),
        ):
            with self.subTest(key=key, value=value):
                config = dict(TEST_CONFIG)
                config[key] = value
                with self.assertRaises(MercadoPagoConfigurationError):
                    MercadoPagoSettings.from_mapping(config)

    def test_client_uses_current_rest_endpoints_and_only_returns_sandbox_url(self):
        session = FakeRequestsSession(
            {
                "id": "preference-1",
                "init_point": "https://production.example.invalid/never-use",
                "sandbox_init_point": "https://sandbox.mercadopago.com/checkout/1",
            }
        )
        client = create_mercado_pago_client(TEST_CONFIG, session=session)
        result = client.create_preference(
            {"items": [{"title": "Test", "quantity": 1, "unit_price": 10.0}]},
            "fitpath-test-reference",
        )
        self.assertEqual(
            result["checkout_url"], "https://sandbox.mercadopago.com/checkout/1"
        )
        method, url, kwargs = session.calls[0]
        self.assertEqual((method, url), ("POST", "https://api.mercadopago.com/checkout/preferences"))
        self.assertEqual(kwargs["headers"]["X-Idempotency-Key"], "fitpath-test-reference")
        self.assertTrue(kwargs["headers"]["Authorization"].startswith("Bearer APP_USR-"))

    def test_webhook_signature_is_constant_time_compatible_and_rejects_replay(self):
        timestamp = str(int(time.time() * 1000))
        request_id = "request-signature-test"
        data_id = "123456"
        manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
        digest = hmac.new(
            TEST_CONFIG["MERCADOPAGO_WEBHOOK_SECRET"].encode(),
            manifest.encode(),
            hashlib.sha256,
        ).hexdigest()
        signature = f"ts={timestamp},v1={digest}"
        self.assertTrue(
            verify_webhook_signature(
                signature,
                request_id,
                data_id,
                TEST_CONFIG["MERCADOPAGO_WEBHOOK_SECRET"],
            )
        )
        with self.assertRaises(WebhookSignatureError):
            verify_webhook_signature(
                signature,
                request_id,
                data_id,
                TEST_CONFIG["MERCADOPAGO_WEBHOOK_SECRET"],
                now_epoch=time.time() + 600,
            )


class PaymentsApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "payments.sqlite3"
        config = {
            "DATABASE": str(self.database_path),
            "SECRET_KEY": "payments-test-only",
            "SESSION_COOKIE_SECURE": False,
            **TEST_CONFIG,
        }
        self.app = create_app("testing", config)
        self.client = self.app.test_client()
        self.db = connect_database(self.database_path)
        self.addCleanup(self.db.close)
        self.assertEqual(
            apply_migrations(self.db, self.app.config["MIGRATIONS_DIR"]),
            (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
        )
        seed_initial_roles(self.db)
        seed_initial_permissions(self.db)
        seed_initial_currencies(self.db)
        self.client_user_id, self.client_id = self._create_client("principal")
        self.other_user_id, self.other_client_id = self._create_client("otro")
        self.membership_id = self.db.execute(
            """
            INSERT INTO membresias
                (nombre, precio_unidades_menores, moneda, descripcion, activa)
            VALUES ('Premium Test', 150000, 'ARS', 'Solo pruebas', 1)
            """
        ).lastrowid
        today = date.today()
        self.subscription_id = self.db.execute(
            """
            INSERT INTO cliente_membresia
                (cliente_id, membresia_id, fecha_inicio, fecha_fin, estado)
            VALUES (?, ?, ?, ?, 'vencida')
            """,
            (
                self.client_id,
                self.membership_id,
                today.isoformat(),
                (today + timedelta(days=30)).isoformat(),
            ),
        ).lastrowid
        self.debt_id = self._create_debt(
            self.client_id, self.subscription_id, "Cuota Premium Test", 150000
        )
        self.other_debt_id = self._create_debt(
            self.other_client_id, None, "Deuda de otro Cliente", 9900
        )
        self.db.commit()
        self.provider = FakeMercadoPago()

    def _create_client(self, suffix):
        role_id = self.db.execute(
            "SELECT id_rol FROM roles WHERE nombre = 'Cliente'"
        ).fetchone()[0]
        user_id = self.db.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES ('Cliente', ?, ?, ?, ?, 1)
            """,
            (suffix, f"payment-{suffix}", f"payment-{suffix}@example.test", role_id),
        ).lastrowid
        client_id = self.db.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (user_id,)
        ).lastrowid
        return user_id, client_id

    def _create_debt(self, client_id, subscription_id, concept, amount):
        return self.db.execute(
            """
            INSERT INTO deudas
                (cliente_id, cliente_membresia_id, concepto,
                 importe_unidades_menores, moneda, vence_el)
            VALUES (?, ?, ?, ?, 'ARS', '2026-12-01')
            """,
            (client_id, subscription_id, concept, amount),
        ).lastrowid

    def _login(self, user_id=None):
        with self.client.session_transaction() as session:
            session["fitpath_user_id"] = user_id or self.client_user_id
            session["csrf_token"] = "payments-csrf"

    def _create_intent(self, debt_id=None, extra=None):
        body = {"debt_id": debt_id or self.debt_id}
        body.update(extra or {})
        with patch(
            "backend.fitpath.api.v1.payments.create_mercado_pago_client",
            return_value=self.provider,
        ):
            return self.client.post(
                "/api/v1/client/payment-intents",
                json=body,
                headers={"X-CSRF-Token": "payments-csrf"},
            )

    def _reference(self, debt_id=None):
        return self.db.execute(
            """
            SELECT referencia_externa
            FROM intentos_pago
            WHERE deuda_id = ?
            ORDER BY id_intento DESC
            LIMIT 1
            """,
            (debt_id or self.debt_id,),
        ).fetchone()[0]

    def _payment(self, payment_id, reference, status, amount=1500.0, live_mode=False):
        return {
            "id": str(payment_id),
            "live_mode": live_mode,
            "external_reference": reference,
            "currency_id": "ARS",
            "transaction_amount": amount,
            "status": status,
            "status_detail": f"test_{status}",
        }

    def _confirm(self, payment_id):
        with patch(
            "backend.fitpath.api.v1.payments.create_mercado_pago_client",
            return_value=self.provider,
        ):
            return self.client.post(
                "/api/v1/client/payment-intents/confirm",
                json={"payment_id": str(payment_id)},
                headers={"X-CSRF-Token": "payments-csrf"},
            )

    def _signed_webhook(self, payment_id, request_id="webhook-request-1", valid=True):
        timestamp = str(int(time.time() * 1000))
        manifest = f"id:{payment_id};request-id:{request_id};ts:{timestamp};"
        digest = hmac.new(
            TEST_CONFIG["MERCADOPAGO_WEBHOOK_SECRET"].encode(),
            manifest.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not valid:
            digest = "0" * 64
        body = {
            "id": "notification-test",
            "live_mode": False,
            "type": "payment",
            "action": "payment.updated",
            "data": {"id": str(payment_id)},
        }
        with patch(
            "backend.fitpath.api.v1.payments.create_mercado_pago_client",
            return_value=self.provider,
        ):
            return self.client.post(
                f"/api/v1/payments/mercado-pago/webhook?data.id={payment_id}&type=payment",
                json=body,
                headers={
                    "X-Request-Id": request_id,
                    "X-Signature": f"ts={timestamp},v1={digest}",
                },
            )

    def test_requires_client_session_permission_csrf_and_own_debt(self):
        self.assertEqual(self.client.get("/api/v1/client/payments").status_code, 401)
        self._login()
        missing_csrf = self.client.post(
            "/api/v1/client/payment-intents", json={"debt_id": self.debt_id}
        )
        self.assertEqual(missing_csrf.status_code, 400)
        foreign = self._create_intent(self.other_debt_id)
        self.assertEqual(foreign.status_code, 404)

    def test_backend_owns_amount_concept_and_returns_only_sandbox_checkout(self):
        self._login()
        response = self._create_intent(extra={"amount": 1, "concept": "alterado"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json["intent"]["checkout_url"].startswith("https://sandbox."))
        payload, idempotency_key = self.provider.preferences[0]
        self.assertEqual(payload["items"][0]["unit_price"], 1500.0)
        self.assertEqual(payload["items"][0]["title"], "Cuota Premium Test")
        self.assertEqual(payload["external_reference"], idempotency_key)
        self.assertEqual(
            payload["notification_url"],
            "https://fitpath.example.test/api/v1/payments/mercado-pago/webhook",
        )
        self.assertNotIn("amount", payload.get("metadata", {}))
        stored = self.db.execute(
            "SELECT estado, importe_unidades_menores FROM intentos_pago"
        ).fetchone()
        self.assertEqual(tuple(stored), ("pendiente", 150000))

    def test_summary_contains_only_authenticated_client_financial_data(self):
        self._login()
        response = self.client.get("/api/v1/client/payments")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([debt["id"] for debt in response.json["debts"]], [self.debt_id])
        self.assertEqual(response.json["membership"]["id"], self.subscription_id)

    def test_pending_approved_and_rejected_results_update_atomically(self):
        self._login()
        self.assertEqual(self._create_intent().status_code, 201)
        reference = self._reference()
        self.provider.payments["101"] = self._payment("101", reference, "pending")
        pending = self._confirm("101")
        self.assertEqual(pending.json["payment"]["status"], "pendiente")

        self.provider.payments["101"] = self._payment("101", reference, "approved")
        approved = self._confirm("101")
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json["payment"]["status"], "aprobado")
        debt = self.db.execute(
            "SELECT estado, pagada_utc FROM deudas WHERE id_deuda = ?",
            (self.debt_id,),
        ).fetchone()
        self.assertEqual(debt["estado"], "pagada")
        self.assertIsNotNone(debt["pagada_utc"])
        self.assertEqual(
            self.db.execute(
                "SELECT estado FROM cliente_membresia WHERE id_cliente_membresia = ?",
                (self.subscription_id,),
            ).fetchone()[0],
            "activa",
        )

        rejected_debt = self._create_debt(
            self.client_id, self.subscription_id, "Cuota rechazada", 50000
        )
        self.db.commit()
        self.assertEqual(self._create_intent(rejected_debt).status_code, 201)
        rejected_reference = self._reference(rejected_debt)
        self.provider.payments["202"] = self._payment(
            "202", rejected_reference, "rejected", amount=500.0
        )
        rejected = self._confirm("202")
        self.assertEqual(rejected.json["payment"]["status"], "rechazado")
        payment_state = self.db.execute(
            """
            SELECT p.estado
            FROM pagos AS p
            JOIN intentos_pago AS i ON i.pago_id = p.id_pago
            WHERE i.deuda_id = ?
            """,
            (rejected_debt,),
        ).fetchone()[0]
        self.assertEqual(payment_state, "anulado")

    def test_provider_live_payment_and_cross_client_confirmation_are_rejected(self):
        self._login()
        self.assertEqual(self._create_intent().status_code, 201)
        reference = self._reference()
        self.provider.payments["303"] = self._payment(
            "303", reference, "approved", live_mode=True
        )
        self.assertEqual(self._confirm("303").status_code, 409)

        self.provider.payments["304"] = self._payment("304", reference, "approved")
        self._login(self.other_user_id)
        self.assertEqual(self._confirm("304").status_code, 404)

    def test_webhook_signature_and_repeated_delivery_are_idempotent(self):
        self._login()
        self.assertEqual(self._create_intent().status_code, 201)
        reference = self._reference()
        self.provider.payments["404"] = self._payment("404", reference, "approved")
        invalid = self._signed_webhook("404", request_id="invalid", valid=False)
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM eventos_webhook_pago").fetchone()[0],
            0,
        )

        first = self._signed_webhook("404")
        repeated = self._signed_webhook("404")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertTrue(repeated.json["result"]["duplicate"])
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM eventos_webhook_pago").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM pagos WHERE deuda_id = ? AND estado = 'realizado'",
                (self.debt_id,),
            ).fetchone()[0],
            1,
        )

    def test_missing_credentials_fail_before_creating_an_intent(self):
        self._login()
        self.app.config["MERCADOPAGO_ACCESS_TOKEN"] = None
        response = self.client.post(
            "/api/v1/client/payment-intents",
            json={"debt_id": self.debt_id},
            headers={"X-CSRF-Token": "payments-csrf"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM intentos_pago").fetchone()[0], 0
        )


if __name__ == "__main__":
    unittest.main()
