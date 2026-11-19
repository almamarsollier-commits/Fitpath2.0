"""Pruebas temporales del catálogo de membresías, suscripciones y pagos."""

import shutil
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from _file_assertions import assert_optional_file_unchanged, snapshot_optional_file
from backend.fitpath.database import connect_database
from backend.fitpath.migrations import MigrationError, apply_migrations
from backend.fitpath.seeds import seed_initial_currencies, seed_initial_roles
from backend.fitpath.services.payments import (
    DebtNotFoundError,
    OverpaymentError,
    PaymentRequestError,
    register_completed_payment,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPOSITORY_ROOT / "backend" / "fitpath" / "migrations"
MIGRATION_VERSIONS = tuple(range(1, 15))
DEFAULT_SUBSCRIPTION = object()


class MembershipPaymentSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "memberships-payments.sqlite3"
        self.connection = connect_database(self.database_path, timeout=10.0)
        self.addCleanup(self.connection.close)
        self.assertEqual(
            apply_migrations(self.connection, MIGRATIONS_DIR),
            MIGRATION_VERSIONS,
        )
        seed_initial_roles(self.connection)
        self.seeded_currencies = seed_initial_currencies(self.connection)
        self.memberships_after_seed = self.connection.execute(
            "SELECT count(*) FROM membresias"
        ).fetchone()[0]
        self.benefits_after_seed = self.connection.execute(
            "SELECT count(*) FROM beneficios"
        ).fetchone()[0]

        self.client_id = self.create_client("principal")
        self.other_client_id = self.create_client("secundario")
        self.membership_id = self.create_membership()
        self.subscription_id = self.create_subscription(self.client_id)
        self.debt_id = self.create_debt(self.client_id, self.subscription_id)
        self.connection.commit()

        legacy_database = REPOSITORY_ROOT / "gimnasio.db"
        self.legacy_metadata = snapshot_optional_file(legacy_database)

    def create_client(self, suffix):
        role_id = self.connection.execute(
            "SELECT id_rol FROM roles WHERE nombre = ?",
            ("Cliente",),
        ).fetchone()[0]
        user_id = self.connection.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Cliente",
                suffix,
                "cliente." + suffix,
                suffix + "@example.test",
                role_id,
            ),
        ).lastrowid
        return self.connection.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)",
            (user_id,),
        ).lastrowid

    def create_membership(
        self, name="Plan de prueba", price=10000, currency="ARS", active=1
    ):
        return self.connection.execute(
            """
            INSERT INTO membresias
                (nombre, precio_unidades_menores, moneda, activa)
            VALUES (?, ?, ?, ?)
            """,
            (name, price, currency, active),
        ).lastrowid

    def create_subscription(
        self,
        client_id=None,
        membership_id=None,
        state="activa",
        start="2026-11-01",
        end=None,
    ):
        return self.connection.execute(
            """
            INSERT INTO cliente_membresia
                (cliente_id, membresia_id, fecha_inicio, fecha_fin, estado)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                client_id if client_id is not None else self.client_id,
                membership_id if membership_id is not None else self.membership_id,
                start,
                end,
                state,
            ),
        ).lastrowid

    def create_debt(
        self,
        client_id=None,
        subscription_id=DEFAULT_SUBSCRIPTION,
        amount=10000,
        currency="ARS",
        due="2026-12-01",
    ):
        return self.connection.execute(
            """
            INSERT INTO deudas
                (cliente_id, cliente_membresia_id, concepto,
                 importe_unidades_menores, moneda, vence_el)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                client_id if client_id is not None else self.client_id,
                subscription_id
                if subscription_id is not DEFAULT_SUBSCRIPTION
                else self.subscription_id,
                "Cuota de prueba",
                amount,
                currency,
                due,
            ),
        ).lastrowid

    def insert_payment(
        self,
        debt_id=None,
        amount=1000,
        method="efectivo",
        state="en_proceso",
        created="2026-11-09T12:00:00Z",
        completed=None,
    ):
        return self.connection.execute(
            """
            INSERT INTO pagos
                (deuda_id, importe_unidades_menores, metodo, estado,
                 creado_utc, realizado_utc)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                debt_id if debt_id is not None else self.debt_id,
                amount,
                method,
                state,
                created,
                completed,
            ),
        ).lastrowid

    def test_migration_creates_all_tables_and_valid_foreign_keys(self):
        expected_tables = {
            "monedas",
            "membresias",
            "beneficios",
            "membresia_beneficio",
            "cliente_membresia",
            "deudas",
            "pagos",
        }
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ?",
                ("table",),
            )
        }
        self.assertTrue(expected_tables.issubset(tables))
        self.assertEqual(self.connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(self.connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(
            self.connection.execute(
                "SELECT version, name FROM schema_migrations WHERE version = ?",
                (6,),
            ).fetchone()["name"],
            "0006_membresias_beneficios_suscripciones_pagos.sql",
        )

    def test_currency_seed_is_only_ars_and_is_idempotent(self):
        self.assertEqual(self.seeded_currencies, ("ARS",))
        self.assertEqual(seed_initial_currencies(self.connection), ())
        self.assertEqual(
            tuple(
                tuple(row)
                for row in self.connection.execute(
                    "SELECT codigo, decimales FROM monedas ORDER BY codigo"
                )
            ),
            (("ARS", 2),),
        )
        self.assertEqual(
            self.memberships_after_seed,
            0,
        )
        self.assertEqual(self.benefits_after_seed, 0)

    def test_currency_and_membership_checks_reject_invalid_values(self):
        for code, decimals in (
            (None, 2),
            ("ars", 2),
            ("AR", 2),
            ("ARS", 5),
            ("USD", 1.5),
        ):
            with self.subTest(code=code, decimals=decimals), self.assertRaises(
                sqlite3.IntegrityError
            ):
                self.connection.execute(
                    "INSERT INTO monedas (codigo, decimales) VALUES (?, ?)",
                    (code, decimals),
                )
        for name, price, currency in (
            (" ", 100, "ARS"),
            ("Plan inválido", -1, "ARS"),
            ("Plan decimal", 1.5, "ARS"),
            ("Plan sin moneda", 100, "XXX"),
        ):
            with self.subTest(name=name), self.assertRaises(sqlite3.IntegrityError):
                self.create_membership(name=name, price=price, currency=currency)

    def test_membership_benefit_is_many_to_many_and_pair_is_unique(self):
        other_membership_id = self.create_membership(name="Plan alternativo")
        benefit_id = self.connection.execute(
            "INSERT INTO beneficios (nombre) VALUES (?)",
            ("Acceso ampliado",),
        ).lastrowid
        self.connection.execute(
            "INSERT INTO membresia_beneficio (membresia_id, beneficio_id) VALUES (?, ?)",
            (self.membership_id, benefit_id),
        )
        self.connection.execute(
            "INSERT INTO membresia_beneficio (membresia_id, beneficio_id) VALUES (?, ?)",
            (other_membership_id, benefit_id),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO membresia_beneficio (membresia_id, beneficio_id) VALUES (?, ?)",
                (self.membership_id, benefit_id),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO membresia_beneficio (membresia_id, beneficio_id) VALUES (?, ?)",
                (999999, benefit_id),
            )
        count = self.connection.execute(
            "SELECT count(*) FROM membresia_beneficio WHERE beneficio_id = ?",
            (benefit_id,),
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_only_one_active_subscription_is_allowed_and_history_is_preserved(self):
        self.create_subscription(
            state="cancelada",
            start="2025-01-01",
            end="2025-06-30",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_subscription(state="activa", start="2026-12-01")
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM cliente_membresia WHERE cliente_id = ?",
                (self.client_id,),
            ).fetchone()[0],
            2,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_subscription(state="suspendida")

    def test_subscription_dates_require_calendar_dates_and_order(self):
        for start, end in (
            ("2026-02-30", None),
            ("2026-01-01", "2025-12-31"),
            ("2026-1-01", None),
        ):
            with self.subTest(start=start, end=end), self.assertRaises(
                sqlite3.IntegrityError
            ):
                self.create_subscription(
                    client_id=self.other_client_id,
                    state="cancelada",
                    start=start,
                    end=end,
                )

    def test_debt_must_reference_an_existing_client_and_matching_subscription(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_debt(client_id=999999)
        with self.assertRaises(sqlite3.IntegrityError):
            self.create_debt(
                client_id=self.other_client_id,
                subscription_id=self.subscription_id,
            )
        debt_without_subscription = self.create_debt(
            client_id=self.other_client_id,
            subscription_id=None,
        )
        self.assertIsNotNone(debt_without_subscription)

    def test_debt_checks_positive_minor_units_currency_and_due_date(self):
        for amount, currency, due in (
            (0, "ARS", "2026-12-01"),
            (-1, "ARS", "2026-12-01"),
            (1.5, "ARS", "2026-12-01"),
            (100, "XXX", "2026-12-01"),
            (100, "ARS", "2026-02-30"),
        ):
            with self.subTest(amount=amount, currency=currency, due=due):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.create_debt(amount=amount, currency=currency, due=due)

    def test_payment_state_method_timestamp_and_amount_constraints(self):
        invalid_payments = (
            (0, "efectivo", "en_proceso", "2026-11-09T12:00:00Z", None),
            (1.5, "efectivo", "en_proceso", "2026-11-09T12:00:00Z", None),
            (1, "tarjeta", "en_proceso", "2026-11-09T12:00:00Z", None),
            (1, "efectivo", "pendiente", "2026-11-09T12:00:00Z", None),
            (1, "efectivo", "realizado", "2026-11-09T12:00:00Z", None),
            (
                1,
                "efectivo",
                "anulado",
                "2026-11-09T12:00:00Z",
                "2026-11-09T12:01:00Z",
            ),
            (1, "efectivo", "en_proceso", "2026-02-30T12:00:00Z", None),
        )
        for amount, method, state, created, completed in invalid_payments:
            with self.subTest(state=state, created=created), self.assertRaises(
                sqlite3.IntegrityError
            ):
                self.insert_payment(
                    amount=amount,
                    method=method,
                    state=state,
                    created=created,
                    completed=completed,
                )
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_payment(debt_id=999999)

    def test_internal_service_records_partial_payments_and_rejects_overpayment(self):
        first_id = register_completed_payment(
            self.connection,
            self.debt_id,
            4000,
            "efectivo",
            "2026-11-09T12:00:00Z",
        )
        second_id = register_completed_payment(
            self.connection,
            self.debt_id,
            6000,
            "transferencia",
            "2026-11-09T12:05:00Z",
        )
        with self.assertRaises(OverpaymentError):
            register_completed_payment(
                self.connection,
                self.debt_id,
                1,
                "digital",
                "2026-11-09T12:10:00Z",
            )
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(
            self.connection.execute(
                "SELECT sum(importe_unidades_menores) FROM pagos WHERE estado = ?",
                ("realizado",),
            ).fetchone()[0],
            10000,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM pagos WHERE id_pago IN (?, ?)",
                (first_id, second_id),
            ).fetchone()[0],
            2,
        )

    def test_payment_service_rejects_invalid_requests_and_missing_debt_cleanly(self):
        with self.assertRaises(PaymentRequestError):
            register_completed_payment(self.connection, self.debt_id, True, "efectivo")
        with self.assertRaises(PaymentRequestError):
            register_completed_payment(self.connection, self.debt_id, 10, "tarjeta")
        with self.assertRaises(PaymentRequestError):
            register_completed_payment(
                self.connection,
                self.debt_id,
                10,
                "efectivo",
                "2026-02-30T12:00:00Z",
            )
        with self.assertRaises(DebtNotFoundError):
            register_completed_payment(self.connection, 999999, 10, "efectivo")
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(
            self.connection.execute("SELECT count(*) FROM pagos").fetchone()[0],
            0,
        )

    def test_concurrent_connections_cannot_overpay_a_debt(self):
        concurrent_debt_id = self.create_debt(amount=10000)
        self.connection.commit()
        barrier = Barrier(2)

        def pay_from_independent_connection():
            connection = connect_database(self.database_path, timeout=10.0)
            try:
                barrier.wait(timeout=5)
                try:
                    register_completed_payment(
                        connection,
                        concurrent_debt_id,
                        6000,
                        "efectivo",
                        "2026-11-09T12:00:00Z",
                    )
                    return "registrado"
                except OverpaymentError:
                    return "saldo_insuficiente"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(
                executor.map(
                    lambda _index: pay_from_independent_connection(),
                    range(2),
                )
            )

        self.assertCountEqual(outcomes, ["registrado", "saldo_insuficiente"])
        total = self.connection.execute(
            "SELECT sum(importe_unidades_menores) FROM pagos WHERE deuda_id = ? AND estado = ?",
            (concurrent_debt_id, "realizado"),
        ).fetchone()[0]
        self.assertEqual(total, 6000)

    def test_migrations_are_idempotent_and_checksum_protected(self):
        self.assertEqual(apply_migrations(self.connection, MIGRATIONS_DIR), ())
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM schema_migrations"
            ).fetchone()[0],
            14,
        )
        copied_migrations = self.root / "checksum-migrations"
        copied_migrations.mkdir()
        for migration in MIGRATIONS_DIR.glob("*.sql"):
            shutil.copyfile(migration, copied_migrations / migration.name)
        connection = connect_database(self.root / "checksum.sqlite3")
        self.addCleanup(connection.close)
        apply_migrations(connection, copied_migrations)
        with (copied_migrations / "0006_membresias_beneficios_suscripciones_pagos.sql").open(
            "a", encoding="utf-8"
        ) as migration_file:
            migration_file.write("\n-- alteración posterior\n")
        with self.assertRaises(MigrationError):
            apply_migrations(connection, copied_migrations)

    def test_failed_migration_rolls_back_all_version_six_objects(self):
        broken_migrations = self.root / "broken-migrations"
        broken_migrations.mkdir()
        for migration in MIGRATIONS_DIR.glob("*.sql"):
            shutil.copyfile(migration, broken_migrations / migration.name)
        version_six = (
            broken_migrations
            / "0006_membresias_beneficios_suscripciones_pagos.sql"
        )
        with version_six.open("a", encoding="utf-8") as migration_file:
            migration_file.write(
                "\nCREATE TABLE rollback_probe (id INTEGER PRIMARY KEY);\n"
                "INVALID SQL;\n"
            )

        connection = connect_database(self.root / "rollback.sqlite3")
        self.addCleanup(connection.close)
        with self.assertRaises(MigrationError):
            apply_migrations(connection, broken_migrations)

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ?",
                ("table",),
            )
        }
        self.assertTrue(
            {
                "progresos",
                "planes_alimentacion",
                "roles",
            }.issubset(tables)
        )
        self.assertTrue(
            {
                "monedas",
                "membresias",
                "beneficios",
                "membresia_beneficio",
                "cliente_membresia",
                "deudas",
                "pagos",
                "rollback_probe",
            }.isdisjoint(tables)
        )
        self.assertEqual(
            tuple(
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ),
            (1, 2, 3, 4, 5),
        )
        self.assertFalse(connection.in_transaction)

    def test_legacy_database_metadata_remains_unchanged(self):
        legacy_database = REPOSITORY_ROOT / "gimnasio.db"
        assert_optional_file_unchanged(self, legacy_database, self.legacy_metadata)


if __name__ == "__main__":
    unittest.main()
