"""Intentos persistentes y reconciliación transaccional de Mercado Pago."""

import hashlib
import hmac
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from .mercado_pago import MercadoPagoError


class PaymentIntentError(RuntimeError):
    """Error controlado del flujo de intentos de pago."""


class PaymentIntentRequestError(PaymentIntentError):
    """La solicitud no cumple el contrato esperado."""


class PaymentIntentNotFoundError(PaymentIntentError):
    """La deuda o el intento no pertenecen al Cliente."""


class PaymentIntentConflictError(PaymentIntentError):
    """Ya existe una operación incompatible o incompleta."""


class PaymentProviderDataError(PaymentIntentError):
    """El pago consultado al proveedor no coincide con el intento local."""


class PaymentIntentStorageError(PaymentIntentError):
    """SQLite no pudo completar el cambio transaccional."""


class WebhookSignatureError(PaymentIntentError):
    """La firma Webhook es inválida o está fuera de la ventana temporal."""


PROVIDER_STATUS = {
    "approved": "aprobado",
    "pending": "pendiente",
    "in_process": "pendiente",
    "authorized": "pendiente",
    "rejected": "rechazado",
    "cancelled": "cancelado",
    "canceled": "cancelado",
}


def _utc_now(now=None):
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _positive_integer(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PaymentIntentRequestError(f"{label} debe ser un entero positivo.")


def _rollback(connection):
    if connection.in_transaction:
        connection.rollback()


def _ensure_connection(connection):
    if connection.in_transaction:
        raise PaymentIntentConflictError(
            "El servicio requiere una conexión sin transacción previa."
        )
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
    if foreign_keys is None or foreign_keys[0] != 1:
        raise PaymentIntentConflictError(
            "El servicio requiere claves foráneas activas."
        )


def _intent_payload(row, reused=False):
    return {
        "id": row["id_intento"],
        "debt_id": row["deuda_id"],
        "reference": row["referencia_externa"],
        "amount_minor": row["importe_unidades_menores"],
        "currency": row["moneda"],
        "currency_decimals": row["decimales"],
        "concept": row["concepto"],
        "status": row["estado"],
        "checkout_url": row["checkout_url"],
        "reused": reused,
    }


def prepare_payment_intent(connection, client_id, debt_id, now=None):
    """Reserva un pago por el saldo backend de una deuda propia."""
    _positive_integer(client_id, "client_id")
    _positive_integer(debt_id, "debt_id")
    _ensure_connection(connection)
    created_at = _utc_now(now)

    try:
        connection.execute("BEGIN IMMEDIATE")
        debt = connection.execute(
            """
            SELECT
                d.id_deuda,
                d.importe_unidades_menores,
                d.moneda,
                d.concepto,
                d.estado,
                m.decimales,
                COALESCE(SUM(
                    CASE WHEN p.estado = 'realizado'
                         THEN p.importe_unidades_menores ELSE 0 END
                ), 0) AS pagado
            FROM deudas AS d
            JOIN monedas AS m ON m.codigo = d.moneda
            LEFT JOIN pagos AS p ON p.deuda_id = d.id_deuda
            WHERE d.id_deuda = ? AND d.cliente_id = ?
            GROUP BY d.id_deuda
            """,
            (debt_id, client_id),
        ).fetchone()
        if debt is None:
            raise PaymentIntentNotFoundError("No existe una deuda propia con ese ID.")

        existing = connection.execute(
            """
            SELECT i.*, m.decimales
            FROM intentos_pago AS i
            JOIN monedas AS m ON m.codigo = i.moneda
            WHERE i.deuda_id = ? AND i.estado IN ('creado', 'pendiente')
            ORDER BY i.id_intento DESC
            LIMIT 1
            """,
            (debt_id,),
        ).fetchone()
        if existing is not None and existing["checkout_url"]:
            connection.commit()
            return _intent_payload(existing, reused=True)
        if existing is not None:
            raise PaymentIntentConflictError(
                "Ya existe un intento en preparación para esta deuda."
            )

        outstanding = debt["importe_unidades_menores"] - debt["pagado"]
        if debt["estado"] != "pendiente" or outstanding <= 0:
            raise PaymentIntentConflictError("La deuda no tiene saldo pendiente.")

        payment_id = connection.execute(
            """
            INSERT INTO pagos
                (deuda_id, importe_unidades_menores, metodo, estado,
                 creado_utc, realizado_utc)
            VALUES (?, ?, 'digital', 'en_proceso', ?, NULL)
            """,
            (debt_id, outstanding, created_at),
        ).lastrowid
        external_reference = f"fitpath_{secrets.token_hex(24)}"
        intent_id = connection.execute(
            """
            INSERT INTO intentos_pago
                (deuda_id, pago_id, referencia_externa,
                 importe_unidades_menores, moneda, concepto, estado,
                 creado_utc, actualizado_utc)
            VALUES (?, ?, ?, ?, ?, ?, 'creado', ?, ?)
            """,
            (
                debt_id,
                payment_id,
                external_reference,
                outstanding,
                debt["moneda"],
                debt["concepto"],
                created_at,
                created_at,
            ),
        ).lastrowid
        row = connection.execute(
            """
            SELECT i.*, m.decimales
            FROM intentos_pago AS i
            JOIN monedas AS m ON m.codigo = i.moneda
            WHERE i.id_intento = ?
            """,
            (intent_id,),
        ).fetchone()
        connection.commit()
        return _intent_payload(row)
    except PaymentIntentError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PaymentIntentStorageError(
            "No se pudo crear el intento de pago."
        ) from error
    except BaseException:
        _rollback(connection)
        raise


def _provider_amount(amount_minor, decimals):
    return float(Decimal(amount_minor) / (Decimal(10) ** decimals))


def build_preference_payload(intent, public_base_url):
    """Construye el monto y concepto únicamente desde el snapshot persistido."""
    return {
        "items": [
            {
                "id": f"deuda-{intent['debt_id']}",
                "title": intent["concept"],
                "quantity": 1,
                "currency_id": intent["currency"],
                "unit_price": _provider_amount(
                    intent["amount_minor"], intent["currency_decimals"]
                ),
            }
        ],
        "external_reference": intent["reference"],
        "back_urls": {
            "success": f"{public_base_url}/templates/cliente/perfil/membresia.html?payment_result=success",
            "pending": f"{public_base_url}/templates/cliente/perfil/membresia.html?payment_result=pending",
            "failure": f"{public_base_url}/templates/cliente/perfil/membresia.html?payment_result=failure",
        },
        "notification_url": (
            f"{public_base_url}/api/v1/payments/mercado-pago/webhook"
        ),
        "auto_return": "approved",
        "metadata": {
            "fitpath_intent_id": intent["id"],
            "fitpath_debt_id": intent["debt_id"],
        },
    }


def attach_provider_preference(
    connection, intent_id, preference_id, checkout_url, now=None
):
    _ensure_connection(connection)
    updated_at = _utc_now(now)
    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            """
            UPDATE intentos_pago
            SET preferencia_proveedor_id = ?, checkout_url = ?,
                estado = 'pendiente', actualizado_utc = ?
            WHERE id_intento = ? AND estado = 'creado'
            """,
            (preference_id, checkout_url, updated_at, intent_id),
        )
        if cursor.rowcount != 1:
            raise PaymentIntentConflictError("El intento ya no puede iniciar checkout.")
        connection.commit()
    except PaymentIntentError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PaymentIntentStorageError(
            "No se pudo asociar la preferencia al intento."
        ) from error


def fail_payment_intent(connection, intent_id, detail="provider_error", now=None):
    _ensure_connection(connection)
    updated_at = _utc_now(now)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT pago_id FROM intentos_pago WHERE id_intento = ? AND estado = 'creado'",
            (intent_id,),
        ).fetchone()
        if row is not None:
            connection.execute(
                """
                UPDATE intentos_pago
                SET estado = 'error', estado_detalle = ?, actualizado_utc = ?
                WHERE id_intento = ?
                """,
                (detail, updated_at, intent_id),
            )
            connection.execute(
                "UPDATE pagos SET estado = 'anulado' WHERE id_pago = ?",
                (row["pago_id"],),
            )
        connection.commit()
    except sqlite3.Error as error:
        _rollback(connection)
        raise PaymentIntentStorageError(
            "No se pudo cerrar el intento fallido."
        ) from error


def create_checkout_intent(connection, client_id, debt_id, provider, now=None):
    intent = prepare_payment_intent(connection, client_id, debt_id, now=now)
    if intent["reused"]:
        return intent
    payload = build_preference_payload(intent, provider.settings.public_base_url)
    try:
        preference = provider.create_preference(payload, intent["reference"])
    except MercadoPagoError:
        fail_payment_intent(connection, intent["id"], now=now)
        raise
    attach_provider_preference(
        connection,
        intent["id"],
        preference["preference_id"],
        preference["checkout_url"],
        now=now,
    )
    intent.update(
        {
            "status": "pendiente",
            "checkout_url": preference["checkout_url"],
            "preference_id": preference["preference_id"],
        }
    )
    return intent


def verify_webhook_signature(
    x_signature,
    x_request_id,
    data_id,
    secret,
    *,
    tolerance_seconds=300,
    now_epoch=None,
):
    """Valida el manifiesto oficial con HMAC-SHA256 y tolerancia anti-replay."""
    signature = str(x_signature or "").strip()
    request_id = str(x_request_id or "").strip()
    resource_id = str(data_id or "").strip()
    secret_value = str(secret or "").strip()
    if (
        not signature
        or len(signature) > 512
        or not request_id
        or len(request_id) > 128
        or not resource_id
        or len(resource_id) > 128
        or not secret_value
    ):
        raise WebhookSignatureError("Faltan datos para validar la firma.")

    timestamp = None
    hashes = []
    for part in signature.split(","):
        key, separator, value = part.strip().partition("=")
        if not separator or not value:
            continue
        if key == "ts" and timestamp is None:
            timestamp = value
        elif key == "v1" and len(value) == 64:
            hashes.append(value.lower())
    if timestamp is None or not timestamp.isdigit() or not hashes:
        raise WebhookSignatureError("La cabecera de firma no es válida.")

    tolerance = int(tolerance_seconds)
    timestamp_seconds = int(timestamp)
    if timestamp_seconds > 100_000_000_000:
        timestamp_seconds /= 1000
    current = time.time() if now_epoch is None else float(now_epoch)
    if tolerance <= 0 or tolerance > 900 or abs(current - timestamp_seconds) > tolerance:
        raise WebhookSignatureError("La firma está fuera de la ventana temporal.")

    manifest = f"id:{resource_id};request-id:{request_id};ts:{timestamp};"
    expected = hmac.new(
        secret_value.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in hashes):
        raise WebhookSignatureError("La firma no coincide.")
    return True


def _provider_payment(payload):
    if not isinstance(payload, dict) or payload.get("live_mode") is not False:
        raise PaymentProviderDataError(
            "Solo se aceptan pagos confirmados como prueba por Mercado Pago."
        )
    provider_id = str(payload.get("id") or "").strip()
    external_reference = str(payload.get("external_reference") or "").strip()
    currency = str(payload.get("currency_id") or "").strip().upper()
    status = str(payload.get("status") or "").strip().lower()
    detail = str(payload.get("status_detail") or "").strip() or None
    if (
        not provider_id
        or len(provider_id) > 128
        or not external_reference
        or status not in PROVIDER_STATUS
    ):
        raise PaymentProviderDataError("El pago del proveedor está incompleto.")
    try:
        amount = Decimal(str(payload.get("transaction_amount")))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise PaymentProviderDataError("El importe del proveedor no es válido.") from error
    if not amount.is_finite() or amount <= 0:
        raise PaymentProviderDataError("El importe del proveedor no es válido.")
    if detail is not None and len(detail) > 255:
        raise PaymentProviderDataError("El detalle del proveedor no es válido.")
    return {
        "provider_id": provider_id,
        "reference": external_reference,
        "currency": currency,
        "status": PROVIDER_STATUS[status],
        "detail": detail,
        "amount": amount,
    }


def _amount_to_minor(amount, decimals):
    scaled = amount * (Decimal(10) ** decimals)
    if scaled != scaled.to_integral_value():
        raise PaymentProviderDataError("El importe no respeta los decimales de la moneda.")
    return int(scaled)


def reconcile_provider_payment(
    connection,
    payload,
    *,
    expected_client_id=None,
    webhook_request_id=None,
    now=None,
):
    """Confirma contra datos del proveedor y actualiza todo en una transacción."""
    payment = _provider_payment(payload)
    if expected_client_id is not None:
        _positive_integer(expected_client_id, "expected_client_id")
    _ensure_connection(connection)
    updated_at = _utc_now(now)

    try:
        connection.execute("BEGIN IMMEDIATE")
        if webhook_request_id:
            duplicate = connection.execute(
                "SELECT 1 FROM eventos_webhook_pago WHERE request_id = ?",
                (webhook_request_id,),
            ).fetchone()
            if duplicate is not None:
                connection.commit()
                return {"duplicate": True, "status": "procesado"}

        intent = connection.execute(
            """
            SELECT
                i.*, d.cliente_id, d.cliente_membresia_id,
                d.importe_unidades_menores AS deuda_importe,
                d.estado AS deuda_estado, m.decimales
            FROM intentos_pago AS i
            JOIN deudas AS d ON d.id_deuda = i.deuda_id
            JOIN monedas AS m ON m.codigo = i.moneda
            WHERE i.referencia_externa = ?
            """,
            (payment["reference"],),
        ).fetchone()
        if intent is None:
            if expected_client_id is not None:
                raise PaymentIntentNotFoundError("El pago no corresponde al Cliente.")
            if webhook_request_id:
                connection.execute(
                    """
                    INSERT INTO eventos_webhook_pago
                        (request_id, recurso_tipo, recurso_id, resultado, recibido_utc)
                    VALUES (?, 'payment', ?, 'ignorado', ?)
                    """,
                    (webhook_request_id, payment["provider_id"], updated_at),
                )
            connection.commit()
            return {"ignored": True, "status": "ignorado"}

        if expected_client_id is not None and intent["cliente_id"] != expected_client_id:
            raise PaymentIntentNotFoundError("El pago no corresponde al Cliente.")
        if intent["moneda"] != payment["currency"]:
            raise PaymentProviderDataError("La moneda no coincide con el intento.")
        amount_minor = _amount_to_minor(payment["amount"], intent["decimales"])
        if amount_minor != intent["importe_unidades_menores"]:
            raise PaymentProviderDataError("El importe no coincide con el intento.")
        if (
            intent["pago_proveedor_id"]
            and intent["pago_proveedor_id"] != payment["provider_id"]
        ):
            raise PaymentProviderDataError("El intento ya pertenece a otro pago.")

        target_status = payment["status"]
        if intent["estado"] == "aprobado" and target_status != "aprobado":
            target_status = "aprobado"

        if target_status == "aprobado" and intent["estado"] != "aprobado":
            other_paid = connection.execute(
                """
                SELECT COALESCE(SUM(importe_unidades_menores), 0)
                FROM pagos
                WHERE deuda_id = ? AND estado = 'realizado' AND id_pago <> ?
                """,
                (intent["deuda_id"], intent["pago_id"]),
            ).fetchone()[0]
            if amount_minor > intent["deuda_importe"] - other_paid:
                raise PaymentIntentConflictError(
                    "La confirmación superaría el saldo de la deuda."
                )
            connection.execute(
                """
                UPDATE pagos
                SET estado = 'realizado', realizado_utc = ?
                WHERE id_pago = ?
                """,
                (updated_at, intent["pago_id"]),
            )
            if other_paid + amount_minor >= intent["deuda_importe"]:
                connection.execute(
                    """
                    UPDATE deudas
                    SET estado = 'pagada', pagada_utc = ?
                    WHERE id_deuda = ?
                    """,
                    (updated_at, intent["deuda_id"]),
                )
                if intent["cliente_membresia_id"] is not None:
                    today = updated_at[:10]
                    connection.execute(
                        """
                        UPDATE cliente_membresia
                        SET estado = 'activa'
                        WHERE id_cliente_membresia = ?
                          AND estado = 'vencida'
                          AND (fecha_fin IS NULL OR fecha_fin >= ?)
                          AND NOT EXISTS (
                              SELECT 1 FROM cliente_membresia AS activa
                              WHERE activa.cliente_id = ?
                                AND activa.estado = 'activa'
                                AND activa.id_cliente_membresia <> ?
                          )
                        """,
                        (
                            intent["cliente_membresia_id"],
                            today,
                            intent["cliente_id"],
                            intent["cliente_membresia_id"],
                        ),
                    )
        elif target_status in {"rechazado", "cancelado"} and intent["estado"] != "aprobado":
            connection.execute(
                """
                UPDATE pagos
                SET estado = 'anulado', realizado_utc = NULL
                WHERE id_pago = ?
                """,
                (intent["pago_id"],),
            )

        connection.execute(
            """
            UPDATE intentos_pago
            SET pago_proveedor_id = ?, estado = ?, estado_detalle = ?,
                actualizado_utc = ?
            WHERE id_intento = ?
            """,
            (
                payment["provider_id"],
                target_status,
                payment["detail"],
                updated_at,
                intent["id_intento"],
            ),
        )
        if webhook_request_id:
            connection.execute(
                """
                INSERT INTO eventos_webhook_pago
                    (request_id, recurso_tipo, recurso_id, resultado, recibido_utc)
                VALUES (?, 'payment', ?, 'procesado', ?)
                """,
                (webhook_request_id, payment["provider_id"], updated_at),
            )
        connection.commit()
        return {
            "duplicate": False,
            "intent_id": intent["id_intento"],
            "debt_id": intent["deuda_id"],
            "status": target_status,
        }
    except PaymentIntentError:
        _rollback(connection)
        raise
    except sqlite3.IntegrityError as error:
        _rollback(connection)
        if webhook_request_id and "eventos_webhook_pago.request_id" in str(error):
            return {"duplicate": True, "status": "procesado"}
        raise PaymentIntentStorageError(
            "No se pudo conciliar el pago."
        ) from error
    except sqlite3.Error as error:
        _rollback(connection)
        raise PaymentIntentStorageError(
            "No se pudo conciliar el pago."
        ) from error
    except BaseException:
        _rollback(connection)
        raise
