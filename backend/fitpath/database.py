"""Conexiones SQLite con claves foráneas activas por conexión."""

import sqlite3
from pathlib import Path

from flask import current_app, g


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LEGACY_DATABASE = REPOSITORY_ROOT / "gimnasio.db"


class DatabaseConfigurationError(RuntimeError):
    """La ruta o la configuración de la base no son seguras."""


def connect_database(database_path, timeout=5.0):
    """Abre la base configurada y verifica la integridad referencial."""
    path = Path(database_path).expanduser().resolve()
    if path == LEGACY_DATABASE.resolve():
        raise DatabaseConfigurationError(
            "El backend nuevo no puede abrir la base heredada."
        )

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(path), timeout=timeout)
    except (OSError, sqlite3.Error) as error:
        raise DatabaseConfigurationError(
            "No se pudo abrir la base configurada."
        ) from error
    connection.row_factory = sqlite3.Row

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        row = connection.execute("PRAGMA foreign_keys").fetchone()
        if row is None or row[0] != 1:
            raise DatabaseConfigurationError(
                "SQLite no activó las claves foráneas para esta conexión."
            )
    except Exception:
        connection.close()
        raise

    return connection


def get_db():
    """Obtiene una conexión por contexto de aplicación, creándola bajo demanda."""
    if "fitpath_db" not in g:
        g.fitpath_db = connect_database(
            current_app.config["DATABASE"],
            timeout=current_app.config["SQLITE_TIMEOUT"],
        )
    return g.fitpath_db


def close_db(_exception=None):
    """Cierra la conexión asociada al contexto actual, si fue abierta."""
    connection = g.pop("fitpath_db", None)
    if connection is not None:
        connection.close()
