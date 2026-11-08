"""Datos de referencia explícitos, independientes de las migraciones."""

import sqlite3


INITIAL_ROLES = (
    "Cliente",
    "Entrenador",
    "Jefe de sede",
    "Administrador",
    "Técnico de mantenimiento",
)


class SeedError(RuntimeError):
    """Los datos existentes impiden aplicar la carga inicial de forma segura."""


def seed_initial_roles(connection):
    """Inserta únicamente los cinco roles aprobados, de forma idempotente."""
    if connection.in_transaction:
        raise SeedError("La carga de roles requiere una conexión sin transacción abierta.")

    inserted = []
    try:
        connection.execute("BEGIN IMMEDIATE")
        for role_name in INITIAL_ROLES:
            existing = connection.execute(
                "SELECT nombre FROM roles WHERE nombre = ? COLLATE NOCASE",
                (role_name,),
            ).fetchone()
            if existing is not None:
                if existing[0] != role_name:
                    raise SeedError(
                        "Hay un rol existente que colisiona con el catálogo inicial."
                    )
                continue

            connection.execute(
                "INSERT INTO roles (nombre) VALUES (?)",
                (role_name,),
            )
            inserted.append(role_name)

        connection.commit()
    except SeedError:
        connection.rollback()
        raise
    except sqlite3.Error as error:
        connection.rollback()
        raise SeedError("No se pudieron cargar los roles iniciales.") from error

    return tuple(inserted)
