"""Administración de catálogos, usuarios, permisos y reportes."""

import re
import sqlite3

from flask import Blueprint, jsonify, request

from ...auth.authorization import current_identity, require_api_access
from ...database import get_db
from ...permissions import (
    ADMIN_DATA_PERMISSION,
    ADMIN_VIEWS_PERMISSION,
    INITIAL_ROLE_PERMISSIONS,
)
from ...services.schedules import validate_timezone_name
from .role_utils import (
    bounded_integer,
    clean_text,
    csrf_is_valid,
    positive_integer,
    require_json_fields,
)


admin_api_blueprint = Blueprint("admin_api", __name__, url_prefix="/api/v1/admin")
admin_required = require_api_access(
    roles=("Administrador",), permission=ADMIN_DATA_PERMISSION
)
USERNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9])?$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MACHINE_STATES = {"operativa", "en_reparacion", "fuera_de_servicio"}


@admin_api_blueprint.after_request
def disable_private_cache(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _users(connection):
    users = [
        dict(row)
        for row in connection.execute(
            """
            SELECT u.id_usuario AS id, u.nombre, u.apellido, u.nombre_usuario,
                   u.email, u.activo, r.id_rol AS rol_id, r.nombre AS rol,
                   (SELECT e.especialidad FROM entrenadores e
                    WHERE e.usuario_id = u.id_usuario) AS especialidad,
                   COALESCE(
                     (SELECT es.sede_id FROM entrenadores e
                      JOIN entrenador_sede es ON es.entrenador_id = e.id_entrenador
                      WHERE e.usuario_id = u.id_usuario
                      ORDER BY es.activo DESC, es.sede_id LIMIT 1),
                     (SELECT j.sede_id FROM jefes_sede j
                      WHERE j.usuario_id = u.id_usuario),
                     (SELECT t.sede_id FROM tecnicos_mantenimiento t
                      WHERE t.usuario_id = u.id_usuario)
                   ) AS sede_id
            FROM usuarios u JOIN roles r ON r.id_rol = u.rol_id
            ORDER BY u.apellido, u.nombre, u.id_usuario
            """
        ).fetchall()
    ]
    for user in users:
        user["activo"] = bool(user["activo"])
    return users


def _sites(connection):
    return [
        dict(row)
        for row in connection.execute(
            "SELECT id_sede AS id, nombre, direccion, zona_horaria FROM sedes ORDER BY nombre"
        ).fetchall()
    ]


def _activities(connection):
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT a.id_actividad AS id, a.nombre,
                   count(ast.sede_id) AS sedes,
                   sum(CASE WHEN ast.habilitada = 1 THEN 1 ELSE 0 END) AS sedes_habilitadas
            FROM actividades a
            LEFT JOIN actividad_sede ast ON ast.actividad_id = a.id_actividad
            GROUP BY a.id_actividad ORDER BY a.nombre
            """
        ).fetchall()
    ]


def _memberships(connection):
    memberships = [
        dict(row)
        for row in connection.execute(
            """
            SELECT m.id_membresia AS id, m.nombre, m.precio_unidades_menores,
                   m.moneda, m.descripcion, m.activa,
                   (SELECT count(*) FROM cliente_membresia cm
                    WHERE cm.membresia_id = m.id_membresia AND cm.estado = 'activa')
                       AS suscripciones_activas
            FROM membresias m ORDER BY m.nombre
            """
        ).fetchall()
    ]
    for membership in memberships:
        benefits = connection.execute(
            """
            SELECT b.id_beneficio AS id, b.nombre
            FROM membresia_beneficio mb
            JOIN beneficios b ON b.id_beneficio = mb.beneficio_id
            WHERE mb.membresia_id = ?
            ORDER BY b.nombre, b.id_beneficio
            """,
            (membership["id"],),
        ).fetchall()
        membership["beneficio_ids"] = [benefit["id"] for benefit in benefits]
        membership["beneficios"] = " · ".join(benefit["nombre"] for benefit in benefits)
    return memberships


def _benefits(connection):
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT b.id_beneficio AS id, b.nombre, b.descripcion,
                   count(mb.membresia_id) AS membresias
            FROM beneficios b
            LEFT JOIN membresia_beneficio mb ON mb.beneficio_id = b.id_beneficio
            GROUP BY b.id_beneficio
            ORDER BY b.nombre, b.id_beneficio
            """
        ).fetchall()
    ]


def _roles(connection):
    roles = [
        dict(row)
        for row in connection.execute(
            "SELECT id_rol AS id, nombre FROM roles ORDER BY id_rol"
        )
    ]
    for role in roles:
        permissions = connection.execute(
            """
            SELECT p.id_permiso AS id, p.clave
            FROM rol_permiso rp
            JOIN permisos p ON p.id_permiso = rp.permiso_id
            WHERE rp.rol_id = ?
            ORDER BY p.clave
            """,
            (role["id"],),
        ).fetchall()
        role["permission_ids"] = [permission["id"] for permission in permissions]
        role["permissions"] = " · ".join(permission["clave"] for permission in permissions)
    return roles


def _permissions(connection):
    return [
        dict(row)
        for row in connection.execute(
            "SELECT id_permiso AS id, clave, descripcion FROM permisos ORDER BY clave"
        )
    ]


def _maintenance(connection):
    machines = [
        dict(row)
        for row in connection.execute(
            """
            SELECT m.id_maquina AS id, s.nombre AS sede, m.tipo, m.estado,
                   (SELECT count(*) FROM tickets_mantenimiento t
                    WHERE t.maquina_id = m.id_maquina
                      AND t.estado IN ('abierto', 'en_proceso')) AS tickets_abiertos
            FROM maquinas m
            JOIN sedes s ON s.id_sede = m.sede_id
            ORDER BY s.nombre, m.tipo, m.id_maquina
            """
        ).fetchall()
    ]
    tickets = [
        dict(row)
        for row in connection.execute(
            """
            SELECT t.id_ticket AS id, s.nombre AS sede, m.tipo AS maquina,
                   u.nombre || ' ' || u.apellido AS tecnico,
                   t.fecha_generacion_utc, t.descripcion, t.estado
            FROM tickets_mantenimiento t
            JOIN maquinas m ON m.id_maquina = t.maquina_id
            JOIN sedes s ON s.id_sede = m.sede_id
            JOIN tecnicos_mantenimiento tm ON tm.id_tecnico = t.tecnico_id
            JOIN usuarios u ON u.id_usuario = tm.usuario_id
            ORDER BY t.fecha_generacion_utc DESC, t.id_ticket DESC
            LIMIT 100
            """
        ).fetchall()
    ]
    history = [
        dict(row)
        for row in connection.execute(
            """
            SELECT h.id_historial AS id, s.nombre AS sede, m.tipo AS maquina,
                   h.ticket_id, h.fecha_utc, h.estado_anterior,
                   h.estado_nuevo, h.descripcion
            FROM historial_mantenimiento h
            JOIN maquinas m ON m.id_maquina = h.maquina_id
            JOIN sedes s ON s.id_sede = m.sede_id
            ORDER BY h.fecha_utc DESC, h.id_historial DESC
            LIMIT 100
            """
        ).fetchall()
    ]
    return machines, tickets, history


def _report(connection):
    return {
        "usuarios_activos": connection.execute("SELECT count(*) FROM usuarios WHERE activo = 1").fetchone()[0],
        "clientes": connection.execute("SELECT count(*) FROM clientes").fetchone()[0],
        "sedes": connection.execute("SELECT count(*) FROM sedes").fetchone()[0],
        "clases_programadas": connection.execute("SELECT count(*) FROM clases WHERE estado = 'programada'").fetchone()[0],
        "inscripciones_activas": connection.execute("SELECT count(*) FROM inscripciones WHERE estado = 'activa'").fetchone()[0],
        "deuda_pendiente_unidades_menores": connection.execute(
            """
            SELECT COALESCE(SUM(d.importe_unidades_menores - COALESCE((
              SELECT SUM(p.importe_unidades_menores) FROM pagos p
              WHERE p.deuda_id = d.id_deuda AND p.estado = 'realizado'
            ), 0)), 0) FROM deudas d WHERE d.estado = 'pendiente'
            """
        ).fetchone()[0],
        "tickets_abiertos": connection.execute(
            "SELECT count(*) FROM tickets_mantenimiento WHERE estado IN ('abierto', 'en_proceso')"
        ).fetchone()[0],
    }


@admin_api_blueprint.get("/dashboard")
@admin_required
def admin_dashboard():
    connection = get_db()
    users = _users(connection)
    sites = _sites(connection)
    activities = _activities(connection)
    memberships = _memberships(connection)
    benefits = _benefits(connection)
    roles = _roles(connection)
    machines, tickets, maintenance_history = _maintenance(connection)
    report = _report(connection)
    return jsonify(
        {
            "metrics": [
                {"label": "Usuarios activos", "value": report["usuarios_activos"]},
                {"label": "Sedes", "value": report["sedes"]},
                {"label": "Clases programadas", "value": report["clases_programadas"]},
            ],
            "sections": [
                {"title": "Usuarios", "rows": users},
                {"title": "Sedes", "rows": sites},
                {"title": "Actividades", "rows": activities},
                {
                    "title": "Membresías",
                    "rows": [
                        {key: value for key, value in membership.items() if key != "beneficio_ids"}
                        for membership in memberships
                    ],
                },
                {"title": "Beneficios", "rows": benefits},
                {
                    "title": "Roles y permisos",
                    "rows": [
                        {key: value for key, value in role.items() if key != "permission_ids"}
                        for role in roles
                    ],
                },
                {"title": "Máquinas", "rows": machines},
                {"title": "Tickets de mantenimiento", "rows": tickets},
                {"title": "Historial de mantenimiento", "rows": maintenance_history},
                {"title": "Reporte operativo", "rows": [report]},
            ],
            "options": {
                "roles": roles,
                "permissions": _permissions(connection),
                "users": users,
                "activities": activities,
                "sites": sites,
                "memberships": memberships,
                "benefits": benefits,
            },
        }
    )


@admin_api_blueprint.get("/reports")
@admin_required
def admin_reports():
    return jsonify({"report": _report(get_db())})


def _person_name(value, field):
    result = clean_text(value, field, maximum=80)
    if not any(character.isalpha() for character in result) or any(
        not (character.isalpha() or character in " '-") for character in result
    ):
        raise ValueError(field)
    return " ".join(result.split())


def _username(value):
    result = clean_text(value, "nombre_usuario", maximum=30).lower()
    if not USERNAME_PATTERN.fullmatch(result):
        raise ValueError("nombre_usuario")
    return result


def _email(value):
    result = clean_text(value, "email", maximum=254).lower()
    if not EMAIL_PATTERN.fullmatch(result):
        raise ValueError("email")
    return result


def _role_and_profile(connection, role_id, payload):
    role = connection.execute(
        "SELECT id_rol, nombre FROM roles WHERE id_rol = ?", (role_id,)
    ).fetchone()
    if role is None:
        return None, None
    profile = {}
    if role["nombre"] == "Entrenador":
        profile["especialidad"] = clean_text(
            payload.get("especialidad"), "especialidad", maximum=120
        )
        profile["sede_id"] = positive_integer(payload.get("sede_id"), "sede_id")
    elif role["nombre"] in {"Jefe de sede", "Técnico de mantenimiento"}:
        profile["sede_id"] = positive_integer(payload.get("sede_id"), "sede_id")
    elif "especialidad" in payload or "sede_id" in payload:
        raise ValueError("role_profile")
    if "sede_id" in profile and connection.execute(
        "SELECT 1 FROM sedes WHERE id_sede = ?", (profile["sede_id"],)
    ).fetchone() is None:
        raise LookupError("site_not_found")
    return role, profile


def _provision_role_profile(connection, user_id, role_name, profile):
    if role_name == "Cliente":
        connection.execute(
            "INSERT OR IGNORE INTO clientes (usuario_id) VALUES (?)", (user_id,)
        )
    elif role_name == "Entrenador":
        trainer = connection.execute(
            "SELECT id_entrenador FROM entrenadores WHERE usuario_id = ?", (user_id,)
        ).fetchone()
        if trainer is None:
            trainer_id = connection.execute(
                "INSERT INTO entrenadores (usuario_id, especialidad) VALUES (?, ?)",
                (user_id, profile["especialidad"]),
            ).lastrowid
        else:
            trainer_id = trainer["id_entrenador"]
            connection.execute(
                "UPDATE entrenadores SET especialidad = ? WHERE id_entrenador = ?",
                (profile["especialidad"], trainer_id),
            )
        connection.execute(
            """
            INSERT INTO entrenador_sede (entrenador_id, sede_id, activo)
            VALUES (?, ?, 1)
            ON CONFLICT(entrenador_id, sede_id) DO UPDATE SET activo = 1
            """,
            (trainer_id, profile["sede_id"]),
        )
    elif role_name == "Jefe de sede":
        connection.execute(
            """
            INSERT INTO jefes_sede (usuario_id, sede_id) VALUES (?, ?)
            ON CONFLICT(usuario_id) DO UPDATE SET sede_id = excluded.sede_id
            """,
            (user_id, profile["sede_id"]),
        )
    elif role_name == "Técnico de mantenimiento":
        connection.execute(
            """
            INSERT INTO tecnicos_mantenimiento (usuario_id, sede_id) VALUES (?, ?)
            ON CONFLICT(usuario_id) DO UPDATE SET sede_id = excluded.sede_id
            """,
            (user_id, profile["sede_id"]),
        )


@admin_api_blueprint.post("/users")
@admin_required
def create_user():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True)
    try:
        require_json_fields(
            payload,
            {
                "nombre", "apellido", "nombre_usuario", "email", "rol_id",
                "especialidad", "sede_id",
            },
            {"nombre", "apellido", "nombre_usuario", "email", "rol_id"},
        )
        values = (
            _person_name(payload["nombre"], "nombre"),
            _person_name(payload["apellido"], "apellido"),
            _username(payload["nombre_usuario"]),
            _email(payload["email"]),
            positive_integer(payload["rol_id"], "rol_id"),
        )
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    try:
        role, profile = _role_and_profile(connection, values[-1], payload)
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    except LookupError:
        return jsonify({"error": "site_not_found"}), 404
    if role is None:
        return jsonify({"error": "role_not_found"}), 404
    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, nombre_usuario, email, rol_id, activo)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            values,
        )
        _provision_role_profile(
            connection, cursor.lastrowid, role["nombre"], profile
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "user_identity_conflict"}), 409
    return jsonify({"user": {"id": cursor.lastrowid}}), 201


@admin_api_blueprint.patch("/users/<int:user_id>")
@admin_required
def update_user(user_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"rol_id", "activo", "especialidad", "sede_id"})
        if not payload:
            raise ValueError("request")
        values = {}
        if "rol_id" in payload:
            values["rol_id"] = positive_integer(payload["rol_id"], "rol_id")
        if "activo" in payload:
            if not isinstance(payload["activo"], bool):
                raise ValueError("activo")
            values["activo"] = int(payload["activo"])
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    identity = current_identity()
    if user_id == identity["user"]["id"] and (
        values.get("activo") == 0 or "rol_id" in values
    ):
        return jsonify({"error": "cannot_change_own_access"}), 409
    connection = get_db()
    target = connection.execute(
        "SELECT id_usuario, rol_id FROM usuarios WHERE id_usuario = ?", (user_id,)
    ).fetchone()
    if target is None:
        return jsonify({"error": "user_not_found"}), 404
    role = None
    profile = None
    if "rol_id" in values:
        try:
            role, profile = _role_and_profile(connection, values["rol_id"], payload)
        except ValueError as validation_error:
            return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
        except LookupError:
            return jsonify({"error": "site_not_found"}), 404
        if role is None:
            return jsonify({"error": "role_not_found"}), 404
    elif "especialidad" in payload or "sede_id" in payload:
        return jsonify({"error": "invalid_request", "field": "rol_id"}), 400
    assignments = ", ".join(f"{field} = ?" for field in values)
    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            f"UPDATE usuarios SET {assignments} WHERE id_usuario = ?",
            (*values.values(), user_id),
        )
        if role is not None:
            _provision_role_profile(connection, user_id, role["nombre"], profile)
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "role_profile_conflict"}), 409
    return jsonify({"user": {"id": user_id, **values}})


@admin_api_blueprint.post("/sites")
@admin_required
def create_site():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"nombre", "direccion", "zona_horaria"}, {"nombre", "direccion", "zona_horaria"})
        values = tuple(clean_text(payload[key], key, maximum=160) for key in ("nombre", "direccion", "zona_horaria"))
        validate_timezone_name(values[2])
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    try:
        cursor = connection.execute(
            "INSERT INTO sedes (nombre, direccion, zona_horaria) VALUES (?, ?, ?)", values
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "site_conflict"}), 409
    return jsonify({"site": {"id": cursor.lastrowid}}), 201


@admin_api_blueprint.patch("/sites/<int:site_id>")
@admin_required
def update_site(site_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"nombre", "direccion", "zona_horaria"})
        if not payload:
            raise ValueError("request")
        values = {key: clean_text(value, key, maximum=160) for key, value in payload.items()}
        if "zona_horaria" in values:
            validate_timezone_name(values["zona_horaria"])
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    assignments = ", ".join(f"{field} = ?" for field in values)
    connection = get_db()
    try:
        cursor = connection.execute(
            f"UPDATE sedes SET {assignments} WHERE id_sede = ?", (*values.values(), site_id)
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "site_conflict"}), 409
    if cursor.rowcount != 1:
        return jsonify({"error": "site_not_found"}), 404
    return jsonify({"site": {"id": site_id, **values}})


@admin_api_blueprint.post("/machines")
@admin_required
def create_machine():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True)
    try:
        require_json_fields(
            payload,
            {"sede_id", "tipo", "estado"},
            {"sede_id", "tipo", "estado"},
        )
        site_id = positive_integer(payload["sede_id"], "sede_id")
        machine_type = clean_text(payload["tipo"], "tipo", maximum=120)
        state = clean_text(payload["estado"], "estado", maximum=30)
        if state not in MACHINE_STATES:
            raise ValueError("estado")
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400

    connection = get_db()
    site = connection.execute(
        "SELECT nombre FROM sedes WHERE id_sede = ?", (site_id,)
    ).fetchone()
    if site is None:
        return jsonify({"error": "site_not_found"}), 404
    try:
        cursor = connection.execute(
            "INSERT INTO maquinas (sede_id, tipo, estado) VALUES (?, ?, ?)",
            (site_id, machine_type, state),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "machine_conflict"}), 409
    return jsonify(
        {
            "machine": {
                "id": cursor.lastrowid,
                "sede_id": site_id,
                "sede": site["nombre"],
                "tipo": machine_type,
                "estado": state,
                "tickets_abiertos": 0,
            }
        }
    ), 201


@admin_api_blueprint.post("/activities")
@admin_required
def create_activity():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"nombre"}, {"nombre"})
        name = clean_text(payload["nombre"], "nombre", maximum=120)
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    try:
        cursor = connection.execute("INSERT INTO actividades (nombre) VALUES (?)", (name,))
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "activity_conflict"}), 409
    return jsonify({"activity": {"id": cursor.lastrowid, "name": name}}), 201


@admin_api_blueprint.patch("/activities/<int:activity_id>")
@admin_required
def update_activity(activity_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"nombre"}, {"nombre"})
        name = clean_text(payload["nombre"], "nombre", maximum=120)
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    try:
        cursor = connection.execute("UPDATE actividades SET nombre = ? WHERE id_actividad = ?", (name, activity_id))
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "activity_conflict"}), 409
    if cursor.rowcount != 1:
        return jsonify({"error": "activity_not_found"}), 404
    return jsonify({"activity": {"id": activity_id, "name": name}})


def _membership_values(payload, partial=False):
    allowed = {"nombre", "precio_unidades_menores", "moneda", "descripcion", "activa"}
    required = set() if partial else {"nombre", "precio_unidades_menores", "moneda"}
    require_json_fields(payload, allowed, required)
    if partial and not payload:
        raise ValueError("request")
    values = {}
    if "nombre" in payload:
        values["nombre"] = clean_text(payload["nombre"], "nombre", maximum=120)
    if "precio_unidades_menores" in payload:
        values["precio_unidades_menores"] = bounded_integer(payload["precio_unidades_menores"], "precio_unidades_menores", 0, 1_000_000_000)
    if "moneda" in payload:
        currency = clean_text(payload["moneda"], "moneda", maximum=3).upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("moneda")
        values["moneda"] = currency
    if "descripcion" in payload:
        values["descripcion"] = clean_text(payload["descripcion"], "descripcion", maximum=1000, optional=True)
    if "activa" in payload:
        if not isinstance(payload["activa"], bool):
            raise ValueError("activa")
        values["activa"] = int(payload["activa"])
    if not partial:
        values.setdefault("descripcion", None)
        values.setdefault("activa", 1)
    return values


@admin_api_blueprint.post("/memberships")
@admin_required
def create_membership():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    try:
        values = _membership_values(request.get_json(silent=True))
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    try:
        cursor = connection.execute(
            """
            INSERT INTO membresias
                (nombre, precio_unidades_menores, moneda, descripcion, activa)
            VALUES (?, ?, ?, ?, ?)
            """,
            tuple(values[key] for key in ("nombre", "precio_unidades_menores", "moneda", "descripcion", "activa")),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "membership_conflict"}), 409
    return jsonify({"membership": {"id": cursor.lastrowid}}), 201


@admin_api_blueprint.patch("/memberships/<int:membership_id>")
@admin_required
def update_membership(membership_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    try:
        values = _membership_values(request.get_json(silent=True), partial=True)
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    assignments = ", ".join(f"{field} = ?" for field in values)
    connection = get_db()
    try:
        cursor = connection.execute(
            f"UPDATE membresias SET {assignments} WHERE id_membresia = ?",
            (*values.values(), membership_id),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "membership_conflict"}), 409
    if cursor.rowcount != 1:
        return jsonify({"error": "membership_not_found"}), 404
    return jsonify({"membership": {"id": membership_id, **values}})


def _benefit_values(payload, partial=False):
    allowed = {"nombre", "descripcion"}
    required = set() if partial else {"nombre"}
    require_json_fields(payload, allowed, required)
    if partial and not payload:
        raise ValueError("request")
    values = {}
    if "nombre" in payload:
        values["nombre"] = clean_text(payload["nombre"], "nombre", maximum=120)
    if "descripcion" in payload:
        values["descripcion"] = clean_text(
            payload["descripcion"], "descripcion", maximum=1000, optional=True
        )
    if not partial:
        values.setdefault("descripcion", None)
    return values


@admin_api_blueprint.post("/benefits")
@admin_required
def create_benefit():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    try:
        values = _benefit_values(request.get_json(silent=True))
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    try:
        cursor = connection.execute(
            "INSERT INTO beneficios (nombre, descripcion) VALUES (?, ?)",
            (values["nombre"], values["descripcion"]),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "benefit_conflict"}), 409
    return jsonify({"benefit": {"id": cursor.lastrowid, **values}}), 201


@admin_api_blueprint.patch("/benefits/<int:benefit_id>")
@admin_required
def update_benefit(benefit_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    try:
        values = _benefit_values(request.get_json(silent=True), partial=True)
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    assignments = ", ".join(f"{field} = ?" for field in values)
    connection = get_db()
    try:
        cursor = connection.execute(
            f"UPDATE beneficios SET {assignments} WHERE id_beneficio = ?",
            (*values.values(), benefit_id),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "benefit_conflict"}), 409
    if cursor.rowcount != 1:
        return jsonify({"error": "benefit_not_found"}), 404
    return jsonify({"benefit": {"id": benefit_id, **values}})


@admin_api_blueprint.put("/memberships/<int:membership_id>/benefits")
@admin_required
def replace_membership_benefits(membership_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"benefit_ids"}, {"benefit_ids"})
        benefit_ids = payload["benefit_ids"]
        if not isinstance(benefit_ids, list):
            raise ValueError("benefit_ids")
        benefit_ids = [positive_integer(value, "benefit_ids") for value in benefit_ids]
        if len(set(benefit_ids)) != len(benefit_ids):
            raise ValueError("benefit_ids")
    except ValueError as validation_error:
        field = str(validation_error) if str(validation_error) else "benefit_ids"
        return jsonify({"error": "invalid_request", "field": field}), 400

    connection = get_db()
    if connection.execute(
        "SELECT 1 FROM membresias WHERE id_membresia = ?", (membership_id,)
    ).fetchone() is None:
        return jsonify({"error": "membership_not_found"}), 404
    if benefit_ids:
        placeholders = ",".join("?" for _ in benefit_ids)
        found = connection.execute(
            f"SELECT count(*) FROM beneficios WHERE id_beneficio IN ({placeholders})",
            benefit_ids,
        ).fetchone()[0]
        if found != len(benefit_ids):
            return jsonify({"error": "benefit_not_found"}), 404
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DELETE FROM membresia_beneficio WHERE membresia_id = ?",
            (membership_id,),
        )
        connection.executemany(
            "INSERT INTO membresia_beneficio (membresia_id, beneficio_id) VALUES (?, ?)",
            ((membership_id, benefit_id) for benefit_id in benefit_ids),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "membership_benefit_conflict"}), 409
    return jsonify(
        {"membership": {"id": membership_id, "benefit_ids": benefit_ids}}
    )


@admin_api_blueprint.get("/permissions")
@admin_required
def list_permissions():
    connection = get_db()
    assignments = [
        dict(row)
        for row in connection.execute(
            """
            SELECT rp.rol_id, rp.permiso_id, r.nombre AS rol, p.clave
            FROM rol_permiso rp
            JOIN roles r ON r.id_rol = rp.rol_id
            JOIN permisos p ON p.id_permiso = rp.permiso_id
            ORDER BY r.id_rol, p.clave
            """
        )
    ]
    return jsonify({"roles": _roles(connection), "permissions": _permissions(connection), "assignments": assignments})


@admin_api_blueprint.put("/roles/<int:role_id>/permissions")
@admin_required
def replace_role_permissions(role_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"permission_ids"}, {"permission_ids"})
        identifiers = payload["permission_ids"]
        if not isinstance(identifiers, list) or len(set(identifiers)) != len(identifiers):
            raise ValueError("permission_ids")
        identifiers = [positive_integer(value, "permission_ids") for value in identifiers]
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    role = connection.execute("SELECT nombre FROM roles WHERE id_rol = ?", (role_id,)).fetchone()
    if role is None:
        return jsonify({"error": "role_not_found"}), 404
    selected_permissions = []
    if identifiers:
        placeholders = ",".join("?" for _ in identifiers)
        selected_permissions = connection.execute(
            f"SELECT id_permiso, clave FROM permisos WHERE id_permiso IN ({placeholders})",
            identifiers,
        ).fetchall()
        if len(selected_permissions) != len(identifiers):
            return jsonify({"error": "permission_not_found"}), 404
    managed_permissions = {
        key: expected_role for key, _description, expected_role in INITIAL_ROLE_PERMISSIONS
    }
    conflicting = [
        row["clave"]
        for row in selected_permissions
        if row["clave"] in managed_permissions
        and managed_permissions[row["clave"]] != role["nombre"]
    ]
    if conflicting:
        return jsonify(
            {"error": "managed_permission_conflict", "permissions": sorted(conflicting)}
        ), 409
    required_keys = {
        key for key, _description, expected_role in INITIAL_ROLE_PERMISSIONS
        if expected_role == role["nombre"]
    }
    selected_keys = {row["clave"] for row in selected_permissions}
    if not required_keys.issubset(selected_keys):
        error = (
            "required_admin_permissions"
            if role["nombre"] == "Administrador"
            else "required_role_permissions"
        )
        return jsonify({"error": error, "permissions": sorted(required_keys)}), 409
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM rol_permiso WHERE rol_id = ?", (role_id,))
        connection.executemany(
            "INSERT INTO rol_permiso (rol_id, permiso_id) VALUES (?, ?)",
            ((role_id, permission_id) for permission_id in identifiers),
        )
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        return jsonify({"error": "permissions_update_failed"}), 500
    return jsonify({"role": {"id": role_id, "permission_ids": identifiers}})
