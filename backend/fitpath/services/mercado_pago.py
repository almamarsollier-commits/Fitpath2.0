"""Cliente HTTP mínimo para Checkout Pro de Mercado Pago en modo de prueba."""

from dataclasses import dataclass
from urllib.parse import urlsplit

import requests


API_BASE_URL = "https://api.mercadopago.com"


class MercadoPagoError(RuntimeError):
    """Error controlado de la integración externa."""


class MercadoPagoConfigurationError(MercadoPagoError):
    """La configuración no garantiza el uso exclusivo del entorno de prueba."""


class MercadoPagoOperationError(MercadoPagoError):
    """La API no respondió con un resultado utilizable."""


def _positive_number(value, label, maximum):
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise MercadoPagoConfigurationError(f"{label} no es válido.") from error
    if parsed <= 0 or parsed > maximum:
        raise MercadoPagoConfigurationError(f"{label} está fuera de rango.")
    return parsed


def _https_base_url(value):
    url = str(value or "").strip().rstrip("/")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise MercadoPagoConfigurationError(
            "Mercado Pago requiere una URL base pública HTTPS."
        )
    return url


@dataclass(frozen=True)
class MercadoPagoSettings:
    access_token: str
    public_base_url: str
    timeout_seconds: float

    @classmethod
    def from_mapping(cls, config):
        scope = str(config.get("MERCADOPAGO_CREDENTIAL_SCOPE") or "").strip().lower()
        if scope != "test":
            raise MercadoPagoConfigurationError(
                "La integración exige confirmar credenciales Mercado Pago de prueba."
            )
        token = str(config.get("MERCADOPAGO_ACCESS_TOKEN") or "").strip()
        if not token.startswith("APP_USR-") or len(token) < 20:
            raise MercadoPagoConfigurationError(
                "Falta un Access Token de prueba con formato esperado."
            )
        return cls(
            access_token=token,
            public_base_url=_https_base_url(
                config.get("MERCADOPAGO_PUBLIC_BASE_URL")
            ),
            timeout_seconds=_positive_number(
                config.get("MERCADOPAGO_TIMEOUT_SECONDS"),
                "MERCADOPAGO_TIMEOUT_SECONDS",
                30,
            ),
        )


class MercadoPagoClient:
    def __init__(self, settings, session=None):
        self.settings = settings
        self.session = session or requests.Session()

    def _request(self, method, path, *, json=None, idempotency_key=None):
        headers = {
            "Authorization": f"Bearer {self.settings.access_token}",
            "Accept": "application/json",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        try:
            response = self.session.request(
                method,
                f"{API_BASE_URL}{path}",
                headers=headers,
                json=json,
                timeout=self.settings.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, TypeError) as error:
            raise MercadoPagoOperationError(
                "Mercado Pago no devolvió una respuesta válida."
            ) from error
        if not isinstance(payload, dict):
            raise MercadoPagoOperationError("La respuesta de Mercado Pago no es válida.")
        return payload

    def create_preference(self, payload, idempotency_key):
        response = self._request(
            "POST",
            "/checkout/preferences",
            json=payload,
            idempotency_key=idempotency_key,
        )
        preference_id = str(response.get("id") or "").strip()
        checkout_url = str(response.get("sandbox_init_point") or "").strip()
        if not preference_id or not checkout_url.startswith("https://"):
            raise MercadoPagoOperationError(
                "Mercado Pago no devolvió un checkout de prueba."
            )
        return {
            "preference_id": preference_id,
            "checkout_url": checkout_url,
        }

    def get_payment(self, payment_id):
        identifier = str(payment_id or "").strip()
        if not identifier.isdigit() or len(identifier) > 32:
            raise MercadoPagoOperationError("El identificador del pago no es válido.")
        return self._request("GET", f"/v1/payments/{identifier}")


def create_mercado_pago_client(config, session=None):
    return MercadoPagoClient(MercadoPagoSettings.from_mapping(config), session=session)
