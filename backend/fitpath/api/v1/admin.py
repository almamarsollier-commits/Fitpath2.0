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


@admin_api_blueprint.after_request
def disable_private_cache(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _users(connection):
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT u.id_usuario AS id, u.nombre, u.apellido, u.nombre_usuario,
                   u.email, u.activo, r.id_rol AS rol_id, r.nombre AS rol
            FROM usuarios u JOIN roles r ON r.id_rol = u.rol_id
            ORDER BY u.apellido, u.nombre, u.id_usuario
            """
        ).fetchall()
    ]


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
    return [
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


def _roles(connection):
    return [dict(row) for row in connection.execute("SELECT id_rol AS id, nombre FROM roles ORDER BY id_rol")]


def _permissions(connection):
    return [
        dict(row)
        for row in connection.execute(
            "SELECT id_permiso AS id, clave, descripcion FROM permisos ORDER BY clave"
        )
    ]


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
                {"title": "Membresías", "rows": memberships},
                {"title": "Reporte operativo", "rows": [report]},
            ],
            "options": {
                "roles": _roles(connection),
                "permissions": _permissions(connection),
                "sites": sites,
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
