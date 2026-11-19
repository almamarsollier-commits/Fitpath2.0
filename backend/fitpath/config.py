"""Configuración separada para desarrollo y pruebas."""

import os
import tempfile
from datetime import timedelta
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_PATH = Path(__file__).resolve().parent / "migrations"


def get_secret_key():
    """Carga la clave Flask prefijada y conserva compatibilidad con SECRET_KEY."""
    return os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SECRET_KEY")


class BaseConfig:
    DATABASE = None
    MIGRATIONS_DIR = MIGRATIONS_PATH
    SQLITE_TIMEOUT = 5.0
    TESTING = False
    SECRET_KEY = None
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.environ.get(
        "GOOGLE_REDIRECT_URI", "http://localhost:5000/auth/google/callback"
    )
    GOOGLE_CALENDAR_REDIRECT_URI = os.environ.get(
        "GOOGLE_CALENDAR_REDIRECT_URI",
        "http://localhost:5000/auth/google/calendar/callback",
    )
    GOOGLE_CALENDAR_TOKEN_SECRET = os.environ.get("GOOGLE_CALENDAR_TOKEN_SECRET")
    GOOGLE_CALENDAR_TIMEOUT_SECONDS = os.environ.get(
        "GOOGLE_CALENDAR_TIMEOUT_SECONDS", "10"
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    S3_BUCKET = os.environ.get("AWS_S3_BUCKET")
    S3_REGION = os.environ.get("AWS_REGION")
    S3_PREFIX = os.environ.get("FITPATH_S3_PREFIX", "fitpath")
    S3_ALLOWED_CONTENT_TYPES = os.environ.get(
        "FITPATH_S3_ALLOWED_CONTENT_TYPES", "image/jpeg,image/png,image/webp"
    )
    S3_MAX_UPLOAD_BYTES = os.environ.get(
        "FITPATH_S3_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)
    )
    S3_DOWNLOAD_TTL_SECONDS = os.environ.get(
        "FITPATH_S3_DOWNLOAD_TTL_SECONDS", "300"
    )
    MERCADOPAGO_ACCESS_TOKEN = os.environ.get("MERCADOPAGO_ACCESS_TOKEN")
    MERCADOPAGO_WEBHOOK_SECRET = os.environ.get("MERCADOPAGO_WEBHOOK_SECRET")
    MERCADOPAGO_PUBLIC_BASE_URL = os.environ.get("MERCADOPAGO_PUBLIC_BASE_URL")
    MERCADOPAGO_CREDENTIAL_SCOPE = os.environ.get("MERCADOPAGO_CREDENTIAL_SCOPE")
    MERCADOPAGO_TIMEOUT_SECONDS = os.environ.get(
        "MERCADOPAGO_TIMEOUT_SECONDS", "10"
    )
    MERCADOPAGO_WEBHOOK_TOLERANCE_SECONDS = os.environ.get(
        "MERCADOPAGO_WEBHOOK_TOLERANCE_SECONDS", "300"
    )
    DEMO_LOGIN_ENABLED = os.environ.get("FITPATH_DEMO_LOGIN_ENABLED") == "1"


class DevelopmentConfig(BaseConfig):
    SESSION_COOKIE_SECURE = False  # Solo para localhost HTTP en desarrollo.
    DATABASE = Path(
        os.environ.get(
            "FITPATH_DEV_DATABASE",
            BACKEND_ROOT / "instance" / "fitpath-development.sqlite3",
        )
    )


class TestingConfig(BaseConfig):
    TESTING = True
    SESSION_COOKIE_SECURE = False
    DATABASE = Path(
        os.environ.get(
            "FITPATH_TEST_DATABASE",
            Path(tempfile.gettempdir()) / "fitpath-tests" / "fitpath-testing.sqlite3",
        )
    )


_CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
}


def get_config(name=None):
    """Devuelve una configuración conocida; no acepta nombres arbitrarios."""
    selected = (name or os.environ.get("FITPATH_ENV", "development")).strip().lower()
    try:
        return _CONFIGS[selected]
    except KeyError as error:
        choices = ", ".join(sorted(_CONFIGS))
        raise ValueError(
            "Entorno FitPath no reconocido: {!r}. Opciones: {}.".format(selected, choices)
        ) from error
