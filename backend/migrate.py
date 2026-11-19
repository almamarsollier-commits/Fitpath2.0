"""Punto de entrada explícito para aplicar migraciones."""

import argparse
import sys

from .fitpath import create_app
from .fitpath.database import DatabaseConfigurationError, get_db
from .fitpath.migrations import MigrationError, apply_migrations


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Aplica migraciones SQL versionadas de FitPath 2.0."
    )
    parser.add_argument(
        "--environment",
        choices=("development", "testing"),
        default=None,
        help="Configuración de base a utilizar (por defecto FITPATH_ENV o development).",
    )
    arguments = parser.parse_args(argv)
    app = create_app(arguments.environment)

    try:
        with app.app_context():
            applied = apply_migrations(
                get_db(),
                app.config["MIGRATIONS_DIR"],
            )
    except (DatabaseConfigurationError, MigrationError) as error:
        print(str(error), file=sys.stderr)
        return 1

    if applied:
        print("Migraciones aplicadas: {}".format(", ".join(map(str, applied))))
    else:
        print("No hay migraciones nuevas para aplicar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
