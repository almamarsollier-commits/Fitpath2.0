"""Datos de referencia explícitos, independientes de las migraciones."""

import sqlite3


INITIAL_ROLES = (
    "Cliente",
    "Entrenador",
    "Jefe de sede",
    "Administrador",
    "Técnico de mantenimiento",
)
INITIAL_CURRENCIES = (("ARS", 2),)


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


def seed_initial_currencies(connection):
    """Carga ARS con dos decimales, sin crear membresías ni importes comerciales."""
    if connection.in_transaction:
        raise SeedError(
            "La carga de monedas requiere una conexión sin transacción abierta."
        )

    inserted = []
    try:
        connection.execute("BEGIN IMMEDIATE")
        for currency_code, decimals in INITIAL_CURRENCIES:
            existing = connection.execute(
                "SELECT decimales FROM monedas WHERE codigo = ?",
                (currency_code,),
            ).fetchone()
            if existing is not None:
                if existing[0] != decimals:
                    raise SeedError(
                        "La moneda existente no coincide con el catálogo inicial."
                    )
                continue

            connection.execute(
                "INSERT INTO monedas (codigo, decimales) VALUES (?, ?)",
                (currency_code, decimals),
            )
            inserted.append(currency_code)

        connection.commit()
    except SeedError:
        connection.rollback()
        raise
    except sqlite3.Error as error:
        connection.rollback()
        raise SeedError("No se pudo cargar la moneda inicial.") from error

    return tuple(inserted)
