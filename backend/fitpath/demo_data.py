"""Datos locales, reproducibles e identificables para demostrar FitPath."""

import argparse
import sqlite3
from datetime import datetime, timedelta, timezone

from . import create_app
from .database import get_db
from .migrations import apply_migrations
from .payments_demo import seed_payment_demo
from .seeds import (
    seed_initial_currencies,
    seed_initial_permissions,
    seed_initial_roles,
)


DEMO_USERS = {
    "client": ("Cliente", "demo.cliente", "cliente.demo@fitpath.example.invalid"),
    "trainer": ("Entrenador", "demo.entrenador", "entrenador.demo@fitpath.example.invalid"),
    "manager": ("Jefe de sede", "demo.jefe", "jefe.demo@fitpath.example.invalid"),
    "admin": ("Administrador", "demo.admin", "admin.demo@fitpath.example.invalid"),
    "technician": (
        "Técnico de mantenimiento",
        "demo.tecnico",
        "tecnico.demo@fitpath.example.invalid",
    ),
}
DEMO_SITE = "FitPath Centro Demo"
DEMO_ACTIVITY = "Funcional FitPath Demo"
DEMO_ROUTINE = "Fuerza funcional · Demo"


def _utc(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _single(connection, query, parameters=()):
    rows = connection.execute(query, parameters).fetchall()
    if len(rows) > 1:
        raise ValueError("Los datos demo existentes son ambiguos.")
    return rows[0] if rows else None


def _user(connection, role_name, username, email):
    role = connection.execute(
        "SELECT id_rol FROM roles WHERE nombre = ?", (role_name,)
    ).fetchone()
    if role is None:
        raise ValueError(f"Falta el rol {role_name}.")
    existing = connection.execute(
        """
        SELECT id_usuario, nombre_usuario, email, rol_id, activo
        FROM usuarios
        WHERE nombre_usuario = ? COLLATE NOCASE OR email = ? COLLATE NOCASE
        """,
        (username, email),
    ).fetchall()
    if existing:
        if len(existing) != 1:
            raise ValueError("El usuario demo colisiona con cuentas distintas.")
        row = existing[0]
        if (
            row["nombre_usuario"] != username
            or row["email"] != email
            or row["rol_id"] != role["id_rol"]
            or row["activo"] != 1
        ):
            raise ValueError("La cuenta demo existente no coincide con su rol aprobado.")
        return row["id_usuario"]
    return connection.execute(
        """
        INSERT INTO usuarios
            (nombre, apellido, nombre_usuario, email, rol_id, activo)
        VALUES ('Demo', ?, ?, ?, ?, 1)
        """,
        (role_name, username, email, role["id_rol"]),
    ).lastrowid


def seed_full_demo(connection, *, confirmed=False, now=None):
    """Carga una sede y operaciones de todos los roles, sin credenciales externas."""
    if not confirmed:
        raise ValueError("La carga demo requiere confirmación explícita.")
    if connection.in_transaction:
        raise ValueError("La conexión no debe tener una transacción abierta.")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now debe incluir zona horaria.")
    current = current.astimezone(timezone.utc).replace(microsecond=0)

    try:
        connection.execute("BEGIN IMMEDIATE")
        users = {
            slug: _user(connection, role, username, email)
            for slug, (role, username, email) in DEMO_USERS.items()
        }

        site = _single(connection, "SELECT id_sede FROM sedes WHERE nombre = ?", (DEMO_SITE,))
        site_id = site["id_sede"] if site else connection.execute(
            "INSERT INTO sedes (nombre, direccion, zona_horaria) VALUES (?, ?, ?)",
            (DEMO_SITE, "Av. Movimiento 2026, Buenos Aires", "America/Argentina/Buenos_Aires"),
        ).lastrowid

        client = connection.execute(
            "SELECT id_cliente FROM clientes WHERE usuario_id = ?", (users["client"],)
        ).fetchone()
        client_id = client["id_cliente"] if client else connection.execute(
            "INSERT INTO clientes (usuario_id) VALUES (?)", (users["client"],)
        ).lastrowid

        trainer = connection.execute(
            "SELECT id_entrenador FROM entrenadores WHERE usuario_id = ?",
            (users["trainer"],),
        ).fetchone()
        trainer_id = trainer["id_entrenador"] if trainer else connection.execute(
            "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, ?)",
            (users["trainer"], "Entrenamiento funcional"),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO entrenador_sede (entrenador_id, sede_id, activo)
            VALUES (?, ?, 1)
            ON CONFLICT(entrenador_id, sede_id) DO UPDATE SET activo = 1
            """,
            (trainer_id, site_id),
        )

        connection.execute(
            "INSERT OR IGNORE INTO jefes_sede (usuario_id, sede_id) VALUES (?, ?)",
            (users["manager"], site_id),
        )
        connection.execute(
            "INSERT OR IGNORE INTO tecnicos_mantenimiento (usuario_id, sede_id) VALUES (?, ?)",
            (users["technician"], site_id),
        )
        technician_id = connection.execute(
            "SELECT id_tecnico FROM tecnicos_mantenimiento WHERE usuario_id = ?",
            (users["technician"],),
        ).fetchone()[0]

        activity = connection.execute(
            "SELECT id_actividad FROM actividades WHERE nombre = ? COLLATE NOCASE",
            (DEMO_ACTIVITY,),
        ).fetchone()
        activity_id = activity["id_actividad"] if activity else connection.execute(
            "INSERT INTO actividades (nombre) VALUES (?)", (DEMO_ACTIVITY,)
        ).lastrowid
        connection.execute(
            """
            INSERT INTO actividad_sede (actividad_id, sede_id, habilitada)
            VALUES (?, ?, 1)
            ON CONFLICT(actividad_id, sede_id) DO UPDATE SET habilitada = 1
            """,
            (activity_id, site_id),
        )

        upcoming = connection.execute(
            """
            SELECT id_clase FROM clases
            WHERE actividad_id = ? AND sede_id = ? AND entrenador_id = ?
              AND estado = 'programada' AND inicio_utc > ?
            ORDER BY inicio_utc LIMIT 1
            """,
            (activity_id, site_id, trainer_id, _utc(current)),
        ).fetchone()
        if upcoming:
            class_id = upcoming["id_clase"]
        else:
            starts = current + timedelta(days=1)
            ends = starts + timedelta(hours=1)
            class_id = connection.execute(
                """
                INSERT INTO clases
                    (actividad_id, sede_id, entrenador_id, inicio_utc,
                     fin_utc, cupo_maximo, estado)
                VALUES (?, ?, ?, ?, ?, 16, 'programada')
                """,
                (activity_id, site_id, trainer_id, _utc(starts), _utc(ends)),
            ).lastrowid
        connection.execute(
            """
            INSERT OR IGNORE INTO inscripciones (cliente_id, clase_id, fecha_utc, estado)
            VALUES (?, ?, ?, 'activa')
            """,
            (client_id, class_id, _utc(current)),
        )

        objective_type = connection.execute(
            "SELECT id_tipo_objetivo FROM tipos_objetivo WHERE nombre = ?",
            ("Rendimiento demo",),
        ).fetchone()
        objective_type_id = objective_type[0] if objective_type else connection.execute(
            "INSERT INTO tipos_objetivo (nombre) VALUES (?)", ("Rendimiento demo",)
        ).lastrowid
        objective = connection.execute(
            "SELECT id_objetivo FROM objetivos WHERE tipo_objetivo_id = ? AND nombre = ?",
            (objective_type_id, "Mejorar fuerza general"),
        ).fetchone()
        objective_id = objective[0] if objective else connection.execute(
            """
            INSERT INTO objetivos (tipo_objetivo_id, nombre, descripcion)
            VALUES (?, ?, ?)
            """,
            (objective_type_id, "Mejorar fuerza general", "Objetivo reproducible de la demostración."),
        ).lastrowid
        connection.execute(
            "INSERT OR IGNORE INTO cliente_objetivo (cliente_id, objetivo_id) VALUES (?, ?)",
            (client_id, objective_id),
        )

        routine = _single(
            connection,
            """
            SELECT id_rutina FROM rutinas
            WHERE nombre = ? AND cliente_id = ? AND entrenador_id = ?
            """,
            (DEMO_ROUTINE, client_id, trainer_id),
        )
        routine_id = routine["id_rutina"] if routine else connection.execute(
            """
            INSERT INTO rutinas
                (nombre, descripcion, fecha_creacion_utc, entrenador_id,
                 cliente_id, objetivo_id, observaciones_entrenador)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DEMO_ROUTINE,
                "Plan de tres ejercicios conectado a datos reales.",
                _utc(current),
                trainer_id,
                client_id,
                objective_id,
                "Priorizar técnica y respetar los descansos.",
            ),
        ).lastrowid
        exercises = (
            ("Sentadilla goblet · Demo", "Piernas", 3, 10, 12000, 75),
            ("Remo con mancuerna · Demo", "Espalda", 3, 12, 8000, 60),
            ("Plancha frontal · Demo", "Core", 3, 30, None, 45),
        )
        for order, (name, group, series, repetitions, weight, rest) in enumerate(exercises, 1):
            exercise = _single(
                connection,
                "SELECT id_ejercicio FROM ejercicios WHERE nombre = ? AND grupo_muscular = ?",
                (name, group),
            )
            exercise_id = exercise[0] if exercise else connection.execute(
                "INSERT INTO ejercicios (nombre, grupo_muscular, descripcion) VALUES (?, ?, ?)",
                (name, group, "Ejercicio de demostración; la indicación profesional prevalece."),
            ).lastrowid
            connection.execute(
                """
                INSERT OR IGNORE INTO rutina_ejercicio
                    (rutina_id, ejercicio_id, orden, series, repeticiones,
                     peso_gramos, descanso_segundos)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (routine_id, exercise_id, order, series, repetitions, weight, rest),
            )

        progress = connection.execute(
            "SELECT 1 FROM progresos WHERE cliente_id = ? AND observaciones = ?",
            (client_id, "Registro inicial de la demostración FitPath."),
        ).fetchone()
        if progress is None:
            connection.execute(
                """
                INSERT INTO progresos
                    (cliente_id, fecha_utc, peso_kg, porcentaje_grasa,
                     rendimiento_ejercicios, observaciones)
                VALUES (?, ?, 68.4, 22.5, ?, ?)
                """,
                (
                    client_id,
                    _utc(current),
                    "Sentadilla goblet: 3 × 10 con 12 kg.",
                    "Registro inicial de la demostración FitPath.",
                ),
            )

        machine = _single(
            connection,
            "SELECT id_maquina FROM maquinas WHERE sede_id = ? AND tipo = ?",
            (site_id, "Bicicleta fija · Demo"),
        )
        machine_id = machine["id_maquina"] if machine else connection.execute(
            "INSERT INTO maquinas (sede_id, tipo, estado) VALUES (?, ?, 'operativa')",
            (site_id, "Bicicleta fija · Demo"),
        ).lastrowid
        ticket = connection.execute(
            """
            SELECT id_ticket FROM tickets_mantenimiento
            WHERE maquina_id = ? AND tecnico_id = ? AND descripcion = ?
            """,
            (machine_id, technician_id, "Control preventivo de pedales y transmisión."),
        ).fetchone()
        if ticket is None:
            connection.execute(
                """
                INSERT INTO tickets_mantenimiento
                    (maquina_id, tecnico_id, fecha_generacion_utc, descripcion, estado)
                VALUES (?, ?, ?, ?, 'abierto')
                """,
                (
                    machine_id,
                    technician_id,
                    _utc(current),
                    "Control preventivo de pedales y transmisión.",
                ),
            )
        connection.commit()
    except (sqlite3.Error, ValueError):
        connection.rollback()
        raise

    payment = seed_payment_demo(connection, users["client"], confirmed=True, today=current.date())
    return {
        "users": users,
        "site_id": site_id,
        "class_id": class_id,
        "routine_id": routine_id,
        "machine_id": machine_id,
        "debt_id": payment["debt_id"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepara datos locales para la demo integral.")
    parser.add_argument(
        "--confirm-development-data",
        action="store_true",
        help="Confirma que se modificará la SQLite local ignorada por Git.",
    )
    args = parser.parse_args(argv)
    if not args.confirm_development_data:
        parser.error("falta --confirm-development-data")
    app = create_app("development")
    with app.app_context():
        connection = get_db()
        apply_migrations(connection, app.config["MIGRATIONS_DIR"])
        seed_initial_roles(connection)
        seed_initial_permissions(connection)
        seed_initial_currencies(connection)
        result = seed_full_demo(connection, confirmed=True)
    print("Demo integral preparada. IDs de usuario: {}".format(result["users"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
