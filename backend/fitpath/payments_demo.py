"""Carga explícita y reversible de una obligación Mercado Pago de demostración."""

import argparse
import sqlite3
from datetime import date, timedelta

from . import create_app
from .database import get_db


DEMO_MEMBERSHIP = "Premium Demo Mercado Pago"
DEMO_PRICE_MINOR = 1_500_000


def seed_payment_demo(connection, user_id, *, confirmed=False, today=None):
    """Crea una membresía vencida y una deuda solo tras confirmación explícita."""
    if not confirmed:
        raise ValueError("La carga demo requiere confirmación explícita.")
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("user_id debe ser un entero positivo.")
    current_date = today or date.today()
    if not isinstance(current_date, date):
        raise ValueError("today debe ser una fecha.")
    if connection.in_transaction:
        raise ValueError("La conexión no debe tener una transacción abierta.")

    try:
        connection.execute("BEGIN IMMEDIATE")
        client = connection.execute(
            """
            SELECT c.id_cliente
            FROM clientes AS c
            JOIN usuarios AS u ON u.id_usuario = c.usuario_id
            JOIN roles AS r ON r.id_rol = u.rol_id
            WHERE u.id_usuario = ? AND u.activo = 1 AND r.nombre = 'Cliente'
            """,
            (user_id,),
        ).fetchone()
        if client is None:
            raise ValueError("El usuario no es un Cliente activo con perfil.")

        membership = connection.execute(
            "SELECT id_membresia, precio_unidades_menores, moneda FROM membresias WHERE nombre = ?",
            (DEMO_MEMBERSHIP,),
        ).fetchone()
        if membership is None:
            membership_id = connection.execute(
                """
                INSERT INTO membresias
                    (nombre, precio_unidades_menores, moneda, descripcion, activa)
                VALUES (?, ?, 'ARS', 'Dato exclusivo para demostración local.', 1)
                """,
                (DEMO_MEMBERSHIP, DEMO_PRICE_MINOR),
            ).lastrowid
        else:
            if (
                membership["precio_unidades_menores"] != DEMO_PRICE_MINOR
                or membership["moneda"] != "ARS"
            ):
                raise ValueError("La membresía demo existente no coincide.")
            membership_id = membership["id_membresia"]

        subscription = connection.execute(
            """
            SELECT id_cliente_membresia
            FROM cliente_membresia
            WHERE cliente_id = ? AND membresia_id = ?
            ORDER BY id_cliente_membresia DESC
            LIMIT 1
            """,
            (client["id_cliente"], membership_id),
        ).fetchone()
        if subscription is None:
            subscription_id = connection.execute(
                """
                INSERT INTO cliente_membresia
                    (cliente_id, membresia_id, fecha_inicio, fecha_fin, estado)
                VALUES (?, ?, ?, ?, 'vencida')
                """,
                (
                    client["id_cliente"],
                    membership_id,
                    current_date.isoformat(),
                    (current_date + timedelta(days=30)).isoformat(),
                ),
            ).lastrowid
        else:
            subscription_id = subscription["id_cliente_membresia"]

        concept = f"DEMO Mercado Pago - {current_date.isoformat()}"
        debt = connection.execute(
            """
            SELECT id_deuda
            FROM deudas
            WHERE cliente_id = ? AND concepto = ?
            """,
            (client["id_cliente"], concept),
        ).fetchone()
        if debt is None:
            debt_id = connection.execute(
                """
                INSERT INTO deudas
                    (cliente_id, cliente_membresia_id, concepto,
                     importe_unidades_menores, moneda, vence_el)
                VALUES (?, ?, ?, ?, 'ARS', ?)
                """,
                (
                    client["id_cliente"],
                    subscription_id,
                    concept,
                    DEMO_PRICE_MINOR,
                    current_date.isoformat(),
                ),
            ).lastrowid
            created = True
        else:
            debt_id = debt["id_deuda"]
            created = False
        connection.commit()
        return {
            "client_id": client["id_cliente"],
            "membership_id": membership_id,
            "subscription_id": subscription_id,
            "debt_id": debt_id,
            "created": created,
        }
    except (ValueError, sqlite3.Error):
        if connection.in_transaction:
            connection.rollback()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Crea datos demo de Mercado Pago en la base de desarrollo."
    )
    parser.add_argument("--user-id", required=True, type=int)
    parser.add_argument(
        "--confirm-development-data",
        action="store_true",
        help="Confirma que se modificará la SQLite local de desarrollo.",
    )
    args = parser.parse_args(argv)
    if not args.confirm_development_data:
        parser.error("falta --confirm-development-data")

    app = create_app("development")
    with app.app_context():
        result = seed_payment_demo(
            get_db(), args.user_id, confirmed=args.confirm_development_data
        )
    action = "creada" if result["created"] else "ya existente"
    print(f"Deuda demo {action}: ID {result['debt_id']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
