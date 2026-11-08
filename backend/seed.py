"""Carga controlada de los roles iniciales, sin usuarios ni permisos."""

import argparse
import sqlite3
import sys

from .fitpath import create_app
from .fitpath.database import DatabaseConfigurationError, get_db
from .fitpath.seeds import SeedError, seed_initial_roles


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Carga los cinco roles de referencia de FitPath 2.0."
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
            inserted = seed_initial_roles(get_db())
    except (DatabaseConfigurationError, SeedError):
        print("No se pudieron cargar los roles iniciales.", file=sys.stderr)
        return 1
    except sqlite3.Error:
        print("No se pudo acceder a la base configurada.", file=sys.stderr)
        return 1

    if inserted:
        print("Roles cargados: {}".format(", ".join(inserted)))
    else:
        print("Los roles iniciales ya estaban cargados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
