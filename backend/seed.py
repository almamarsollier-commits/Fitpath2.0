"""Carga controlada de roles y moneda inicial, sin usuarios ni credenciales."""

import argparse
import sqlite3
import sys

from .fitpath import create_app
from .fitpath.database import DatabaseConfigurationError, get_db
from .fitpath.seeds import (
    SeedError,
    seed_initial_currencies,
    seed_initial_roles,
)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Carga los roles y la moneda de referencia de FitPath 2.0."
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=("development", "testing"),
        help="Entorno explícito para seleccionar la base configurada.",
    )
    arguments = parser.parse_args(argv)
    app = create_app(arguments.environment)

    try:
        with app.app_context():
            connection = get_db()
            inserted_roles = seed_initial_roles(connection)
            inserted_currencies = seed_initial_currencies(connection)
    except (DatabaseConfigurationError, SeedError):
        print("No se pudieron cargar los datos de referencia iniciales.", file=sys.stderr)
        return 1
    except sqlite3.Error:
        print("No se pudo acceder a la base configurada.", file=sys.stderr)
        return 1

    if inserted_roles or inserted_currencies:
        if inserted_roles:
            print("Roles cargados: {}".format(", ".join(inserted_roles)))
        if inserted_currencies:
            print("Monedas cargadas: {}".format(", ".join(inserted_currencies)))
    else:
        print("Los datos de referencia iniciales ya estaban cargados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
