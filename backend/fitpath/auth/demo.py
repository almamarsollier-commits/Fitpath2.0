"""Aprovisionamiento local idempotente de una cuenta ficticia Cliente."""

import sqlite3
import sys

from .. import create_app
from ..database import get_db


DEMO_USER = {
    "nombre": "Demo",
    "apellido": "Cliente M11",
    "nombre_usuario": "m11_demo_cliente",
    "email": "m11-demo-cliente@example.invalid",
}


def create_local_client(connection, *, nombre, apellido, nombre_usuario, email):
    """Crea de forma idempotente un usuario Cliente local y su perfil."""
    user_data = {
        "nombre": nombre,
        "apellido": apellido,
        "nombre_usuario": nombre_usuario,
        "email": email,
    }
    for key, value in user_data.items():
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ValueError("Los datos del usuario deben ser textos no vacíos y sin espacios externos.")
        if key in {"nombre_usuario", "email"} and value != value.lower():
            raise ValueError("El nombre de usuario y el email deben estar en minúsculas.")

    try:
        connection.execute("BEGIN IMMEDIATE")
        role = connection.execute(
            "SELECT id_rol FROM roles WHERE nombre = ? COLLATE NOCASE",
            ("Cliente",),
        ).fetchone()
        if role is None:
            raise ValueError("El rol Cliente no está disponible.")

        matches = connection.execute(
            """
            SELECT id_usuario, nombre, apellido, nombre_usuario, email, rol_id, activo
            FROM usuarios
            WHERE nombre_usuario = ? COLLATE NOCASE OR email = ? COLLATE NOCASE
            """,
            (user_data["nombre_usuario"], user_data["email"]),
        ).fetchall()
        if matches:
            if len(matches) != 1:
                raise ValueError("El nombre de usuario y el email coinciden con cuentas distintas.")
            user = matches[0]
            expected = (
                user_data["nombre"],
                user_data["apellido"],
                user_data["nombre_usuario"],
                user_data["email"],
                role["id_rol"],
                1,
            )
            actual = tuple(
                user[key]
                for key in (
                    "nombre",
                    "apellido",
                    "nombre_usuario",
                    "email",
                    "rol_id",
                    "activo",
                )
            )
            if actual != expected:
                raise ValueError("La cuenta existente no coincide con los datos autorizados.")
            user_id = user["id_usuario"]
            created = False
        else:
            cursor = connection.execute(
                """
                INSERT INTO usuarios
                    (nombre, apellido, nombre_usuario, email, rol_id, activo)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    user_data["nombre"],
                    user_data["apellido"],
                    user_data["nombre_usuario"],
                    user_data["email"],
                    role["id_rol"],
                ),
            )
            user_id = cursor.lastrowid
            created = True

        profile = connection.execute(
            "SELECT id_cliente FROM clientes WHERE usuario_id = ?", (user_id,)
        ).fetchone()
        if profile is None:
            connection.execute("INSERT INTO clientes (usuario_id) VALUES (?)", (user_id,))

        connection.commit()
        return user_id, created
    except Exception:
        connection.rollback()
        raise


def create_demo_client(connection):
    """Crea usuario activo y perfil Cliente, sin rol extra ni identidad Google."""
    return create_local_client(connection, **DEMO_USER)


def main():
    app = create_app("development")
    try:
        with app.app_context():
            user_id, created = create_demo_client(get_db())
    except (sqlite3.Error, ValueError):
        print("No se pudo preparar la cuenta local de demostración.", file=sys.stderr)
        return 1

    state = "creada" if created else "ya existente"
    print("Cuenta Cliente demo {}. ID FitPath: {}.".format(state, user_id))
    print("No se creó identidad Google ni se asignaron permisos adicionales.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
