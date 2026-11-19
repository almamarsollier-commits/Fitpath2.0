"""Registro interno de pagos ya realizados, sin pasarela ni endpoint."""

import re
import sqlite3
from datetime import datetime, timezone


ALLOWED_METHODS = frozenset({"efectivo", "transferencia", "digital"})
UTC_TIMESTAMP = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)


class PaymentError(RuntimeError):
    """Error controlado al registrar un pago interno."""


class PaymentRequestError(PaymentError):
    """Los datos de entrada del pago no son válidos."""


class PaymentConfigurationError(PaymentError):
    """La conexión no cumple las garantías requeridas."""


class DebtNotFoundError(PaymentError):
    """No existe la deuda indicada."""


class OverpaymentError(PaymentError):
    """El pago supera el saldo pendiente de la deuda."""


class PaymentStorageError(PaymentError):
    """SQLite no pudo registrar el pago."""


def _positive_integer(value, field_name):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PaymentRequestError("{} debe ser un entero positivo.".format(field_name))


def _validated_timestamp(value):
    if not isinstance(value, str) or UTC_TIMESTAMP.fullmatch(value) is None:
        raise PaymentRequestError("realizado_utc debe ser una fecha UTC canónica.")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise PaymentRequestError(
            "realizado_utc debe ser una fecha UTC válida."
        ) from error
    return value


def _rollback_if_needed(connection):
    if connection.in_transaction:
        connection.rollback()


def register_completed_payment(
    connection, deuda_id, importe_unidades_menores, metodo, realizado_utc=None
):
    """Registra un pago ya recibido, sin cobrar ni autorizar al solicitante.

    Debe mantenerse como operación interna hasta que existan autenticación y
    autorización reales. BEGIN IMMEDIATE serializa a los escritores de SQLite
    mientras se calcula el saldo y se inserta el pago confirmado.
    """
    _positive_integer(deuda_id, "deuda_id")
    _positive_integer(importe_unidades_menores, "importe_unidades_menores")
    if not isinstance(metodo, str) or metodo not in ALLOWED_METHODS:
        raise PaymentRequestError("El método de pago no está permitido.")

    occurred_at = _validated_timestamp(
        realizado_utc
        if realizado_utc is not None
        else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if connection.in_transaction:
        raise PaymentConfigurationError(
            "El servicio requiere una conexión sin transacción previa."
        )
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
    if foreign_keys is None or foreign_keys[0] != 1:
        raise PaymentConfigurationError(
            "El servicio requiere claves foráneas activas."
        )

    try:
        connection.execute("BEGIN IMMEDIATE")
        debt = connection.execute(
            "SELECT importe_unidades_menores FROM deudas WHERE id_deuda = ?",
            (deuda_id,),
        ).fetchone()
        if debt is None:
            raise DebtNotFoundError("No existe la deuda indicada.")

        paid = connection.execute(
            """
            SELECT COALESCE(sum(importe_unidades_menores), 0)
            FROM pagos
            WHERE deuda_id = ? AND estado = ?
            """,
            (deuda_id, "realizado"),
        ).fetchone()[0]
        if importe_unidades_menores > debt[0] - paid:
            raise OverpaymentError("El pago supera el saldo pendiente de la deuda.")

        cursor = connection.execute(
            """
            INSERT INTO pagos
                (deuda_id, importe_unidades_menores, metodo, estado,
                 creado_utc, realizado_utc)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                deuda_id,
                importe_unidades_menores,
                metodo,
                "realizado",
                created_at,
                occurred_at,
            ),
        )
        payment_id = cursor.lastrowid
        connection.commit()
        return payment_id
    except PaymentError:
        _rollback_if_needed(connection)
        raise
    except sqlite3.Error as error:
        _rollback_if_needed(connection)
        raise PaymentStorageError("No se pudo registrar el pago.") from error
    except BaseException:
        _rollback_if_needed(connection)
        raise
