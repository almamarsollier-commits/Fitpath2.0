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
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)


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
