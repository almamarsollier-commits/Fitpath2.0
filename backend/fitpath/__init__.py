"""Aplicación Flask de FitPath 2.0."""

import os

from flask import Flask

from .config import get_config, get_secret_key
from .database import close_db


def create_app(config_name=None, test_config=None):
    """Crea la app sin abrir SQLite; registra autenticación y vistas Cliente."""
    app = Flask(__name__, static_folder=None)
    app.config.from_object(get_config(config_name))
    app.config["SECRET_KEY"] = get_secret_key()

    if test_config:
        app.config.update(test_config)

    if not app.config.get("DATABASE"):
        raise ValueError("La configuración debe definir DATABASE.")

    app.config["DATABASE"] = os.fspath(app.config["DATABASE"])
    app.config["MIGRATIONS_DIR"] = os.fspath(app.config["MIGRATIONS_DIR"])
    app.teardown_appcontext(close_db)

    from .auth import init_auth
    from .api.v1 import init_api_v1

    init_auth(app)
    init_api_v1(app)
    return app
