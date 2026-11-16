"""Membresías, deudas e intentos Checkout Pro del Cliente autenticado."""

import hmac

from flask import Blueprint, current_app, jsonify, request

from ...auth.authorization import current_identity, require_api_access
from ...database import get_db
from ...permissions import CLIENT_DATA_PERMISSION
from ...services.mercado_pago import (
    MercadoPagoConfigurationError,
    MercadoPagoOperationError,
    MercadoPagoSettings,
    create_mercado_pago_client,
)
from ...services.payment_intents import (
    PaymentIntentConflictError,
    PaymentIntentError,
    PaymentIntentNotFoundError,
    PaymentIntentRequestError,
    PaymentProviderDataError,
    WebhookSignatureError,
    create_checkout_intent,
    reconcile_provider_payment,
    verify_webhook_signature,
)


payments_api_blueprint = Blueprint("payments_api", __name__, url_prefix="/api/v1")
client_payment_required = require_api_access(
    roles=("Cliente",), permission=CLIENT_DATA_PERMISSION
)


@payments_api_blueprint.after_request
def disable_private_cache(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _client_id():
    identity = current_identity()
    row = get_db().execute(
        "SELECT id_cliente FROM clientes WHERE usuario_id = ?",
        (identity["user"]["id"],),
    ).fetchone()
    return row["id_cliente"] if row else None


def _csrf_is_valid():
    identity = current_identity()
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = identity["csrf_token"] if identity else ""
    return bool(supplied and expected and hmac.compare_digest(supplied, expected))


def _checkout_is_configured():
    try:
        MercadoPagoSettings.from_mapping(current_app.config)
        return True
    except MercadoPagoConfigurationError:
        return False


def _payment_summary(client_id):
    connection = get_db()
    membership = connection.execute(
        """
        SELECT
            cm.id_cliente_membresia AS id,
            m.nombre,
            cm.estado,
            cm.fecha_inicio,
            cm.fecha_fin
        FROM cliente_membresia AS cm
        JOIN membresias AS m ON m.id_membresia = cm.membresia_id
        WHERE cm.cliente_id = ?
        ORDER BY
            CASE cm.estado WHEN 'activa' THEN 0 WHEN 'vencida' THEN 1 ELSE 2 END,
            cm.fecha_inicio DESC,
            cm.id_cliente_membresia DESC
        LIMIT 1
        """,
        (client_id,),
    ).fetchone()
    debts = connection.execute(
        """
        SELECT
            d.id_deuda,
            d.concepto,
            d.importe_unidades_menores,
            d.moneda,
            d.vence_el,
            d.estado,
            d.pagada_utc,
            m.decimales,
            COALESCE(SUM(
                CASE WHEN p.estado = 'realizado'
                     THEN p.importe_unidades_menores ELSE 0 END
            ), 0) AS pagado
        FROM deudas AS d
        JOIN monedas AS m ON m.codigo = d.moneda
        LEFT JOIN pagos AS p ON p.deuda_id = d.id_deuda
        WHERE d.cliente_id = ?
        GROUP BY d.id_deuda
        ORDER BY d.vence_el DESC, d.id_deuda DESC
        """,
        (client_id,),
    ).fetchall()
    history = connection.execute(
        """
        SELECT
            i.id_intento,
            i.deuda_id,
            i.importe_unidades_menores,
            i.moneda,
            i.concepto,
            i.estado,
            i.estado_detalle,
            i.creado_utc,
            i.actualizado_utc,
            m.decimales
        FROM intentos_pago AS i
        JOIN deudas AS d ON d.id_deuda = i.deuda_id
        JOIN monedas AS m ON m.codigo = i.moneda
        WHERE d.cliente_id = ?
        ORDER BY i.creado_utc DESC, i.id_intento DESC
        LIMIT 30
        """,
        (client_id,),
    ).fetchall()
    return {
        "checkout_available": _checkout_is_configured(),
        "membership": dict(membership) if membership else None,
        "debts": [
            {
                "id": row["id_deuda"],
                "concept": row["concepto"],
                "amount_minor": row["importe_unidades_menores"],
                "paid_minor": row["pagado"],
                "outstanding_minor": max(
                    0, row["importe_unidades_menores"] - row["pagado"]
                ),
                "currency": row["moneda"],
                "currency_decimals": row["decimales"],
                "due_on": row["vence_el"],
                "status": row["estado"],
                "paid_at": row["pagada_utc"],
            }
            for row in debts
        ],
        "history": [
            {
                "id": row["id_intento"],
                "debt_id": row["deuda_id"],
                "amount_minor": row["importe_unidades_menores"],
                "currency": row["moneda"],
                "currency_decimals": row["decimales"],
                "concept": row["concepto"],
                "status": row["estado"],
                "status_detail": row["estado_detalle"],
                "created_at": row["creado_utc"],
                "updated_at": row["actualizado_utc"],
            }
            for row in history
        ],
    }


@payments_api_blueprint.get("/client/payments")
@client_payment_required
def client_payments():
    client_id = _client_id()
    if client_id is None:
        return jsonify({"error": "client_profile_required"}), 403
    return jsonify(_payment_summary(client_id))


@payments_api_blueprint.post("/client/payment-intents")
@client_payment_required
def create_payment_intent():
    if not _csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    client_id = _client_id()
    if client_id is None:
        return jsonify({"error": "client_profile_required"}), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_request"}), 400
    debt_id = payload.get("debt_id")
    try:
        provider = create_mercado_pago_client(current_app.config)
        intent = create_checkout_intent(get_db(), client_id, debt_id, provider)
        return jsonify(
            {
                "intent": {
                    "id": intent["id"],
                    "debt_id": intent["debt_id"],
                    "amount_minor": intent["amount_minor"],
                    "currency": intent["currency"],
                    "status": intent["status"],
                    "checkout_url": intent["checkout_url"],
                    "reused": intent["reused"],
                }
            }
        ), 201
    except MercadoPagoConfigurationError:
        return jsonify({"error": "payments_not_configured"}), 503
    except MercadoPagoOperationError:
        return jsonify({"error": "payment_provider_unavailable"}), 502
    except PaymentIntentNotFoundError:
        return jsonify({"error": "debt_not_found"}), 404
    except PaymentIntentRequestError:
        return jsonify({"error": "invalid_request"}), 400
    except PaymentIntentConflictError as error:
        return jsonify({"error": "payment_conflict", "message": str(error)}), 409
    except PaymentIntentError:
        current_app.logger.exception("No se pudo crear el intento de pago.")
        return jsonify({"error": "payment_intent_failed"}), 500


@payments_api_blueprint.post("/client/payment-intents/confirm")
@client_payment_required
def confirm_payment_intent():
    if not _csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    client_id = _client_id()
    if client_id is None:
        return jsonify({"error": "client_profile_required"}), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_request"}), 400
    payment_id = payload.get("payment_id")
    try:
        provider = create_mercado_pago_client(current_app.config)
        provider_payment = provider.get_payment(payment_id)
        result = reconcile_provider_payment(
            get_db(), provider_payment, expected_client_id=client_id
        )
        return jsonify({"payment": result})
    except MercadoPagoConfigurationError:
        return jsonify({"error": "payments_not_configured"}), 503
    except MercadoPagoOperationError:
        return jsonify({"error": "payment_provider_unavailable"}), 502
    except PaymentIntentNotFoundError:
        return jsonify({"error": "payment_not_found"}), 404
    except (PaymentProviderDataError, PaymentIntentConflictError):
        return jsonify({"error": "payment_confirmation_rejected"}), 409
    except PaymentIntentError:
        current_app.logger.exception("No se pudo confirmar el pago.")
        return jsonify({"error": "payment_confirmation_failed"}), 500


def _webhook_tolerance():
    try:
        value = int(current_app.config["MERCADOPAGO_WEBHOOK_TOLERANCE_SECONDS"])
    except (KeyError, TypeError, ValueError) as error:
        raise MercadoPagoConfigurationError(
            "La tolerancia del Webhook no es válida."
        ) from error
    if value <= 0 or value > 900:
        raise MercadoPagoConfigurationError(
            "La tolerancia del Webhook no es válida."
        )
    return value


@payments_api_blueprint.post("/payments/mercado-pago/webhook")
def mercado_pago_webhook():
    data_id = request.args.get("data.id", "")
    topic = request.args.get("type", "")
    payload = request.get_json(silent=True)
    payload_data = payload.get("data") if isinstance(payload, dict) else None
    if (
        topic != "payment"
        or not isinstance(payload, dict)
        or not isinstance(payload_data, dict)
        or payload.get("type") != "payment"
        or str(payload_data.get("id", "")) != data_id
        or payload.get("live_mode") is not False
    ):
        return jsonify({"error": "invalid_webhook"}), 400

    request_id = request.headers.get("X-Request-Id", "")
    try:
        if str(current_app.config.get("MERCADOPAGO_CREDENTIAL_SCOPE") or "").lower() != "test":
            raise MercadoPagoConfigurationError("El Webhook exige entorno de prueba.")
        verify_webhook_signature(
            request.headers.get("X-Signature"),
            request_id,
            data_id,
            current_app.config.get("MERCADOPAGO_WEBHOOK_SECRET"),
            tolerance_seconds=_webhook_tolerance(),
        )
        provider = create_mercado_pago_client(current_app.config)
        provider_payment = provider.get_payment(data_id)
        result = reconcile_provider_payment(
            get_db(),
            provider_payment,
            webhook_request_id=request_id,
        )
        return jsonify({"received": True, "result": result}), 200
    except WebhookSignatureError:
        return jsonify({"error": "invalid_webhook_signature"}), 401
    except MercadoPagoConfigurationError:
        return jsonify({"error": "payments_not_configured"}), 503
    except MercadoPagoOperationError:
        return jsonify({"error": "payment_provider_unavailable"}), 502
    except (PaymentProviderDataError, PaymentIntentConflictError):
        return jsonify({"error": "payment_reconciliation_rejected"}), 409
    except PaymentIntentError:
        current_app.logger.exception("No se pudo procesar el Webhook de pago.")
        return jsonify({"error": "webhook_processing_failed"}), 500
