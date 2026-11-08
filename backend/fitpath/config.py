"""Configuración separada para desarrollo y pruebas."""

import os
import tempfile
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_PATH = Path(__file__).resolve().parent / "migrations"


class BaseConfig:
    DATABASE = None
    MIGRATIONS_DIR = MIGRATIONS_PATH
    SQLITE_TIMEOUT = 5.0
    TESTING = False


class DevelopmentConfig(BaseConfig):
    DATABASE = Path(
        os.environ.get(
            "FITPATH_DEV_DATABASE",
            BACKEND_ROOT / "instance" / "fitpath-development.sqlite3",
        )
    )


class TestingConfig(BaseConfig):
    TESTING = True
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
