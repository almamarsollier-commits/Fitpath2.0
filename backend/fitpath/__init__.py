"""Aplicación Flask de FitPath 2.0."""

import os

from flask import Flask

from .config import get_config
from .database import close_db


def create_app(config_name=None, test_config=None):
    """Crea la aplicación sin abrir la base de datos ni registrar rutas privadas."""
    app = Flask(__name__, static_folder=None)
    app.config.from_object(get_config(config_name))

    if test_config:
        app.config.update(test_config)

    if not app.config.get("DATABASE"):
        raise ValueError("La configuración debe definir DATABASE.")

    app.config["DATABASE"] = os.fspath(app.config["DATABASE"])
    app.config["MIGRATIONS_DIR"] = os.fspath(app.config["MIGRATIONS_DIR"])
    app.teardown_appcontext(close_db)
    return app
