"""Operación limitada a la sede del Jefe autenticado."""

import re
import sqlite3

from flask import Blueprint, current_app, jsonify, request

from ...auth.authorization import current_identity, require_api_access
from ...database import get_db
from ...permissions import MANAGER_DATA_PERMISSION
from .role_utils import (
    bounded_integer,
    clean_text,
    csrf_is_valid,
    positive_integer,
    require_json_fields,
    utc_now,
)


manager_api_blueprint = Blueprint("manager_api", __name__, url_prefix="/api/v1/manager")
manager_required = require_api_access(
    roles=("Jefe de sede",), permission=MANAGER_DATA_PERMISSION
)
UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@manager_api_blueprint.after_request
def disable_private_cache(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _manager_profile():
    identity = current_identity()
    return get_db().execute(
        """
        SELECT j.id_jefe_sede, j.sede_id, s.nombre AS sede
        FROM jefes_sede j
        JOIN sedes s ON s.id_sede = j.sede_id
        WHERE j.usuario_id = ?
        """,
        (identity["user"]["id"],),
    ).fetchone()


def _profile_or_error():
    profile = _manager_profile()
    if profile is None:
        return None, (jsonify({"error": "manager_profile_required"}), 403)
    return profile, None


def _dashboard_payload(site_id):
    connection = get_db()
    personnel = [
        dict(row)
        for row in connection.execute(
            """
            SELECT DISTINCT u.id_usuario AS id, u.nombre, u.apellido, r.nombre AS rol,
                   CASE WHEN r.nombre = 'Entrenador' THEN COALESCE((
                     SELECT es.activo FROM entrenadores e
                     JOIN entrenador_sede es ON es.entrenador_id = e.id_entrenador
                     WHERE e.usuario_id = u.id_usuario AND es.sede_id = ?
                   ), 0) ELSE 1 END AS vinculo_activo
            FROM usuarios u
            JOIN roles r ON r.id_rol = u.rol_id
            WHERE u.activo = 1 AND (
              EXISTS (SELECT 1 FROM entrenadores e JOIN entrenador_sede es
                      ON es.entrenador_id = e.id_entrenador
                      WHERE e.usuario_id = u.id_usuario AND es.sede_id = ?)
              OR EXISTS (SELECT 1 FROM tecnicos_mantenimiento t
                         WHERE t.usuario_id = u.id_usuario AND t.sede_id = ?)
              OR EXISTS (SELECT 1 FROM jefes_sede j
                         WHERE j.usuario_id = u.id_usuario AND j.sede_id = ?)
            )
            ORDER BY r.nombre, u.apellido, u.nombre
            """,
            (site_id, site_id, site_id, site_id),
        ).fetchall()
    ]
    activities = [
        dict(row)
        for row in connection.execute(
            """
            SELECT a.id_actividad AS id, a.nombre, ast.habilitada
            FROM actividad_sede ast
            JOIN actividades a ON a.id_actividad = ast.actividad_id
            WHERE ast.sede_id = ? ORDER BY a.nombre
            """,
            (site_id,),
        ).fetchall()
    ]
    classes = [
        dict(row)
        for row in connection.execute(
            """
            SELECT c.id_clase AS id, a.nombre AS actividad,
                   u.nombre || ' ' || u.apellido AS entrenador,
                   c.inicio_utc, c.fin_utc, c.cupo_maximo, c.estado,
                   (SELECT count(*) FROM inscripciones i
                    WHERE i.clase_id = c.id_clase AND i.estado = 'activa') AS inscriptos
            FROM clases c
            JOIN actividades a ON a.id_actividad = c.actividad_id
            JOIN entrenadores e ON e.id_entrenador = c.entrenador_id
            JOIN usuarios u ON u.id_usuario = e.usuario_id
            WHERE c.sede_id = ? ORDER BY c.inicio_utc DESC LIMIT 100
            """,
            (site_id,),
        ).fetchall()
    ]
    trainers = [
        dict(row)
        for row in connection.execute(
            """
            SELECT e.id_entrenador AS id, u.nombre || ' ' || u.apellido AS nombre
            FROM entrenador_sede es
            JOIN entrenadores e ON e.id_entrenador = es.entrenador_id
            JOIN usuarios u ON u.id_usuario = e.usuario_id
            WHERE es.sede_id = ? AND es.activo = 1 AND u.activo = 1
            ORDER BY u.apellido, u.nombre
            """,
            (site_id,),
        ).fetchall()
    ]
    return {
        "metrics": [
            {"label": "Personal activo", "value": len(personnel)},
            {"label": "Actividades", "value": len(activities)},
            {"label": "Clases registradas", "value": len(classes)},
        ],
        "sections": [
            {"title": "Personal de la sede", "rows": personnel},
            {"title": "Actividades", "rows": activities},
            {"title": "Horarios y cupos", "rows": classes},
        ],
        "options": {"activities": activities, "trainers": trainers},
    }


@manager_api_blueprint.get("/dashboard")
@manager_required
def manager_dashboard():
    profile, error = _profile_or_error()
    if error:
        return error
    payload = _dashboard_payload(profile["sede_id"])
    payload["site"] = {"id": profile["sede_id"], "name": profile["sede"]}
    return jsonify(payload)


@manager_api_blueprint.patch("/personnel/<int:user_id>")
@manager_required
def update_site_personnel(user_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or set(payload) != {"activo_en_sede"}
        or not isinstance(payload["activo_en_sede"], bool)
    ):
        return jsonify({"error": "invalid_request"}), 400
    connection = get_db()
    trainer = connection.execute(
        """
        SELECT e.id_entrenador, es.activo
        FROM entrenadores e
        JOIN entrenador_sede es ON es.entrenador_id = e.id_entrenador
        WHERE e.usuario_id = ? AND es.sede_id = ?
        """,
        (user_id, profile["sede_id"]),
    ).fetchone()
    if trainer is None:
        return jsonify({"error": "site_personnel_not_found"}), 404
    enabled = int(payload["activo_en_sede"])
    if enabled == trainer["activo"]:
        return jsonify({"personnel": {"user_id": user_id, "active": bool(enabled)}})
    if not enabled and connection.execute(
        """
        SELECT 1 FROM clases
        WHERE entrenador_id = ? AND sede_id = ? AND estado = 'programada'
          AND inicio_utc > ? LIMIT 1
        """,
        (trainer["id_entrenador"], profile["sede_id"], utc_now()),
    ).fetchone() is not None:
        return jsonify({"error": "trainer_has_scheduled_classes"}), 409
    connection.execute(
        "UPDATE entrenador_sede SET activo = ? WHERE entrenador_id = ? AND sede_id = ?",
        (enabled, trainer["id_entrenador"], profile["sede_id"]),
    )
    connection.commit()
    return jsonify({"personnel": {"user_id": user_id, "active": bool(enabled)}})


@manager_api_blueprint.post("/activities")
@manager_required
def create_site_activity():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"nombre"}, {"nombre"})
        name = clean_text(payload["nombre"], "nombre", maximum=120)
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    try:
        connection.execute("BEGIN IMMEDIATE")
        activity = connection.execute(
            "SELECT id_actividad FROM actividades WHERE nombre = ? COLLATE NOCASE",
            (name,),
        ).fetchone()
        if activity is None:
            activity_id = connection.execute(
                "INSERT INTO actividades (nombre) VALUES (?)", (name,)
            ).lastrowid
        else:
            activity_id = activity["id_actividad"]
        connection.execute(
            "INSERT INTO actividad_sede (actividad_id, sede_id, habilitada) VALUES (?, ?, 1)",
            (activity_id, profile["sede_id"]),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "activity_already_linked"}), 409
    return jsonify({"activity": {"id": activity_id, "name": name}}), 201


@manager_api_blueprint.patch("/activities/<int:activity_id>")
@manager_required
def update_site_activity(activity_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"habilitada"} or not isinstance(payload["habilitada"], bool):
        return jsonify({"error": "invalid_request"}), 400
    connection = get_db()
    cursor = connection.execute(
        "UPDATE actividad_sede SET habilitada = ? WHERE actividad_id = ? AND sede_id = ?",
        (int(payload["habilitada"]), activity_id, profile["sede_id"]),
    )
    connection.commit()
    if cursor.rowcount != 1:
        return jsonify({"error": "activity_not_found"}), 404
    return jsonify({"activity": {"id": activity_id, "enabled": payload["habilitada"]}})


def _class_values(payload, *, partial=False):
    allowed = {"actividad_id", "entrenador_id", "inicio_utc", "fin_utc", "cupo_maximo", "estado"}
    required = set() if partial else allowed - {"estado"}
    require_json_fields(payload, allowed, required)
    if partial and not payload:
        raise ValueError("request")
    values = {}
    for key in ("actividad_id", "entrenador_id"):
        if key in payload:
            values[key] = positive_integer(payload[key], key)
    if "cupo_maximo" in payload:
        values["cupo_maximo"] = bounded_integer(payload["cupo_maximo"], "cupo_maximo", 1, 10000)
    for key in ("inicio_utc", "fin_utc"):
        if key in payload:
            value = clean_text(payload[key], key, maximum=20)
            if not UTC_PATTERN.fullmatch(value):
                raise ValueError(key)
            values[key] = value
    if "estado" in payload:
        if payload["estado"] not in {"programada", "cancelada", "realizada"}:
            raise ValueError("estado")
        values["estado"] = payload["estado"]
    if not partial:
        values.setdefault("estado", "programada")
        if values["fin_utc"] <= values["inicio_utc"]:
            raise ValueError("horario")
    return values


@manager_api_blueprint.post("/classes")
@manager_required
def create_site_class():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    try:
        values = _class_values(request.get_json(silent=True))
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    try:
        cursor = connection.execute(
            """
            INSERT INTO clases
                (actividad_id, sede_id, entrenador_id, inicio_utc, fin_utc,
                 cupo_maximo, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values["actividad_id"], profile["sede_id"], values["entrenador_id"],
                values["inicio_utc"], values["fin_utc"], values["cupo_maximo"],
                values["estado"],
            ),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "class_relationship_conflict"}), 409
    return jsonify({"class": {"id": cursor.lastrowid}}), 201


@manager_api_blueprint.patch("/classes/<int:class_id>")
@manager_required
def update_site_class(class_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    try:
        values = _class_values(request.get_json(silent=True), partial=True)
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    current = connection.execute(
        "SELECT * FROM clases WHERE id_clase = ? AND sede_id = ?",
        (class_id, profile["sede_id"]),
    ).fetchone()
    if current is None:
        return jsonify({"error": "class_not_found"}), 404
    start = values.get("inicio_utc", current["inicio_utc"])
    end = values.get("fin_utc", current["fin_utc"])
    if end <= start:
        return jsonify({"error": "invalid_request", "field": "horario"}), 400
    if "cupo_maximo" in values:
        occupied = connection.execute(
            "SELECT count(*) FROM inscripciones WHERE clase_id = ? AND estado = 'activa'",
            (class_id,),
        ).fetchone()[0]
        if values["cupo_maximo"] < occupied:
            return jsonify({"error": "capacity_below_enrollments"}), 409
    assignments = ", ".join(f"{field} = ?" for field in values)
    try:
        connection.execute(
            f"UPDATE clases SET {assignments} WHERE id_clase = ? AND sede_id = ?",
            (*values.values(), class_id, profile["sede_id"]),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "class_relationship_conflict"}), 409
    return jsonify({"class": {"id": class_id, **values}})
