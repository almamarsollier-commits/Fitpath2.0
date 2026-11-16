"""Gestión autorizada del Entrenador."""

import re
import sqlite3

from flask import Blueprint, current_app, jsonify, request

from ...auth.authorization import current_identity, require_api_access
from ...database import get_db
from ...permissions import TRAINER_DATA_PERMISSION
from .role_utils import (
    bounded_integer,
    clean_text,
    csrf_is_valid,
    positive_integer,
    require_json_fields,
    utc_now,
)


trainer_api_blueprint = Blueprint("trainer_api", __name__, url_prefix="/api/v1/trainer")
trainer_required = require_api_access(
    roles=("Entrenador",), permission=TRAINER_DATA_PERMISSION
)
TIME_PATTERN = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")


@trainer_api_blueprint.after_request
def disable_private_cache(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _trainer_profile():
    identity = current_identity()
    return get_db().execute(
        "SELECT id_entrenador, especialidad FROM entrenadores WHERE usuario_id = ?",
        (identity["user"]["id"],),
    ).fetchone()


def _profile_or_error():
    profile = _trainer_profile()
    if profile is None:
        return None, (jsonify({"error": "trainer_profile_required"}), 403)
    return profile, None


def _authorized_client(connection, trainer_id, client_id):
    return connection.execute(
        """
        SELECT 1
        FROM inscripciones AS i
        JOIN clases AS c ON c.id_clase = i.clase_id
        WHERE i.cliente_id = ? AND c.entrenador_id = ?
        LIMIT 1
        """,
        (client_id, trainer_id),
    ).fetchone() is not None


def _dashboard_payload(trainer_id):
    connection = get_db()
    classes = [
        dict(row)
        for row in connection.execute(
            """
            SELECT c.id_clase AS id, a.nombre AS actividad, s.nombre AS sede,
                   c.inicio_utc, c.fin_utc, c.cupo_maximo, c.estado,
                   (SELECT count(*) FROM inscripciones i
                    WHERE i.clase_id = c.id_clase AND i.estado = 'activa') AS inscriptos
            FROM clases c
            JOIN actividades a ON a.id_actividad = c.actividad_id
            JOIN sedes s ON s.id_sede = c.sede_id
            WHERE c.entrenador_id = ?
            ORDER BY c.inicio_utc DESC LIMIT 50
            """,
            (trainer_id,),
        ).fetchall()
    ]
    students = [
        dict(row)
        for row in connection.execute(
            """
            SELECT DISTINCT cl.id_cliente AS id, u.nombre, u.apellido,
                   count(DISTINCT i.id_inscripcion) AS inscripciones
            FROM clientes cl
            JOIN usuarios u ON u.id_usuario = cl.usuario_id
            JOIN inscripciones i ON i.cliente_id = cl.id_cliente
            JOIN clases c ON c.id_clase = i.clase_id
            WHERE c.entrenador_id = ? AND u.activo = 1
            GROUP BY cl.id_cliente
            ORDER BY u.apellido, u.nombre
            """,
            (trainer_id,),
        ).fetchall()
    ]
    routines = [
        dict(row)
        for row in connection.execute(
            """
            SELECT r.id_rutina AS id, r.nombre, r.descripcion,
                   r.fecha_creacion_utc, r.cliente_id,
                   u.nombre || ' ' || u.apellido AS cliente,
                   (SELECT count(*) FROM rutina_ejercicio re
                    WHERE re.rutina_id = r.id_rutina) AS ejercicios
            FROM rutinas r
            JOIN clientes cl ON cl.id_cliente = r.cliente_id
            JOIN usuarios u ON u.id_usuario = cl.usuario_id
            WHERE r.entrenador_id = ?
            ORDER BY r.fecha_creacion_utc DESC, r.id_rutina DESC
            """,
            (trainer_id,),
        ).fetchall()
    ]
    availability = [
        dict(row)
        for row in connection.execute(
            """
            SELECT d.id_disponibilidad AS id, d.sede_id, s.nombre AS sede,
                   d.dia_semana, d.hora_inicio, d.hora_fin
            FROM disponibilidad_entrenador d
            JOIN sedes s ON s.id_sede = d.sede_id
            WHERE d.entrenador_id = ?
            ORDER BY d.dia_semana, d.hora_inicio
            """,
            (trainer_id,),
        ).fetchall()
    ]
    exercises = [
        dict(row)
        for row in connection.execute(
            """
            SELECT id_ejercicio AS id, nombre, grupo_muscular, descripcion
            FROM ejercicios ORDER BY nombre, id_ejercicio
            """
        ).fetchall()
    ]
    sites = [
        dict(row)
        for row in connection.execute(
            """
            SELECT s.id_sede AS id, s.nombre
            FROM entrenador_sede es
            JOIN sedes s ON s.id_sede = es.sede_id
            WHERE es.entrenador_id = ? AND es.activo = 1
            ORDER BY s.nombre
            """,
            (trainer_id,),
        ).fetchall()
    ]
    remuneration = [
        dict(row)
        for row in connection.execute(
            """
            SELECT r.id_remuneracion AS id, r.importe_unidades_menores,
                   r.moneda, r.estado_liquidacion, r.liquidada_utc,
                   c.inicio_utc, a.nombre AS actividad
            FROM remuneraciones r
            JOIN clases c ON c.id_clase = r.clase_id
            JOIN actividades a ON a.id_actividad = c.actividad_id
            WHERE c.entrenador_id = ?
            ORDER BY c.inicio_utc DESC
            """,
            (trainer_id,),
        ).fetchall()
    ]
    enrollments = [
        dict(row)
        for row in connection.execute(
            """
            SELECT i.id_inscripcion AS id,
                   u.nombre || ' ' || u.apellido AS alumno,
                   a.nombre AS actividad, c.inicio_utc,
                   COALESCE(ast.estado, 'sin_registrar') AS asistencia
            FROM inscripciones i
            JOIN clientes cl ON cl.id_cliente = i.cliente_id
            JOIN usuarios u ON u.id_usuario = cl.usuario_id
            JOIN clases c ON c.id_clase = i.clase_id
            JOIN actividades a ON a.id_actividad = c.actividad_id
            LEFT JOIN asistencias ast ON ast.inscripcion_id = i.id_inscripcion
            WHERE c.entrenador_id = ? AND i.estado = 'activa'
            ORDER BY c.inicio_utc DESC, u.apellido, u.nombre
            """,
            (trainer_id,),
        ).fetchall()
    ]
    return {
        "metrics": [
            {"label": "Clases asignadas", "value": len(classes)},
            {"label": "Alumnos autorizados", "value": len(students)},
            {"label": "Rutinas creadas", "value": len(routines)},
        ],
        "sections": [
            {"title": "Clases asignadas", "rows": classes},
            {"title": "Alumnos autorizados", "rows": students},
            {"title": "Rutinas", "rows": routines},
            {"title": "Ejercicios", "rows": exercises},
            {"title": "Disponibilidad", "rows": availability},
            {"title": "Asistencias", "rows": enrollments},
            {"title": "Remuneraciones", "rows": remuneration},
        ],
        "options": {
            "students": students,
            "sites": sites,
            "enrollments": enrollments,
            "routines": routines,
            "exercises": exercises,
        },
    }


@trainer_api_blueprint.get("/dashboard")
@trainer_required
def trainer_dashboard():
    profile, error = _profile_or_error()
    if error:
        return error
    return jsonify(_dashboard_payload(profile["id_entrenador"]))


@trainer_api_blueprint.post("/routines")
@trainer_required
def create_routine():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    payload = request.get_json(silent=True)
    try:
        require_json_fields(
            payload,
            {"nombre", "descripcion", "cliente_id", "objetivo_id", "observaciones"},
            {"nombre", "cliente_id"},
        )
        name = clean_text(payload["nombre"], "nombre", maximum=120)
        description = clean_text(payload.get("descripcion"), "descripcion", maximum=1000, optional=True)
        client_id = positive_integer(payload["cliente_id"], "cliente_id")
        objective_id = payload.get("objetivo_id")
        if objective_id is not None:
            objective_id = positive_integer(objective_id, "objetivo_id")
        observations = clean_text(
            payload.get("observaciones"), "observaciones", maximum=1000, optional=True
        )
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    if not _authorized_client(connection, profile["id_entrenador"], client_id):
        return jsonify({"error": "student_not_authorized"}), 403
    if objective_id is not None and connection.execute(
        "SELECT 1 FROM cliente_objetivo WHERE cliente_id = ? AND objetivo_id = ?",
        (client_id, objective_id),
    ).fetchone() is None:
        return jsonify({"error": "objective_not_assigned_to_client"}), 409
    try:
        cursor = connection.execute(
            """
            INSERT INTO rutinas
                (nombre, descripcion, fecha_creacion_utc, entrenador_id,
                 cliente_id, objetivo_id, observaciones_entrenador)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                description,
                utc_now(),
                profile["id_entrenador"],
                client_id,
                objective_id,
                observations,
            ),
        )
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        current_app.logger.exception("No se pudo crear la rutina.")
        return jsonify({"error": "routine_create_failed"}), 500
    return jsonify({"routine": {"id": cursor.lastrowid}}), 201


@trainer_api_blueprint.patch("/routines/<int:routine_id>")
@trainer_required
def update_routine(routine_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"nombre", "descripcion", "observaciones"})
        if not payload:
            raise ValueError("request")
        values = {}
        if "nombre" in payload:
            values["nombre"] = clean_text(payload["nombre"], "nombre", maximum=120)
        if "descripcion" in payload:
            values["descripcion"] = clean_text(payload["descripcion"], "descripcion", maximum=1000, optional=True)
        if "observaciones" in payload:
            values["observaciones_entrenador"] = clean_text(payload["observaciones"], "observaciones", maximum=1000, optional=True)
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    if connection.execute(
        "SELECT 1 FROM rutinas WHERE id_rutina = ? AND entrenador_id = ?",
        (routine_id, profile["id_entrenador"]),
    ).fetchone() is None:
        return jsonify({"error": "routine_not_found"}), 404
    assignments = ", ".join(f"{field} = ?" for field in values)
    connection.execute(
        f"UPDATE rutinas SET {assignments} WHERE id_rutina = ?",
        (*values.values(), routine_id),
    )
    connection.commit()
    return jsonify({"routine": {"id": routine_id, **values}})


@trainer_api_blueprint.post("/exercises")
@trainer_required
def create_exercise():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"nombre", "grupo_muscular", "descripcion"}, {"nombre"})
        values = (
            clean_text(payload["nombre"], "nombre", maximum=120),
            clean_text(payload.get("grupo_muscular"), "grupo_muscular", maximum=120, optional=True),
            clean_text(payload.get("descripcion"), "descripcion", maximum=1000, optional=True),
        )
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    cursor = connection.execute(
        "INSERT INTO ejercicios (nombre, grupo_muscular, descripcion) VALUES (?, ?, ?)",
        values,
    )
    connection.commit()
    return jsonify({"exercise": {"id": cursor.lastrowid}}), 201


@trainer_api_blueprint.patch("/exercises/<int:exercise_id>")
@trainer_required
def update_exercise(exercise_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"nombre", "grupo_muscular", "descripcion"})
        if not payload:
            raise ValueError("request")
        values = {
            key: clean_text(
                value,
                key,
                maximum=120 if key != "descripcion" else 1000,
                optional=key != "nombre",
            )
            for key, value in payload.items()
        }
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    assignments = ", ".join(f"{field} = ?" for field in values)
    connection = get_db()
    cursor = connection.execute(
        f"UPDATE ejercicios SET {assignments} WHERE id_ejercicio = ?",
        (*values.values(), exercise_id),
    )
    connection.commit()
    if cursor.rowcount != 1:
        return jsonify({"error": "exercise_not_found"}), 404
    return jsonify({"exercise": {"id": exercise_id, **values}})


@trainer_api_blueprint.post("/routines/<int:routine_id>/exercises")
@trainer_required
def add_routine_exercise(routine_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    payload = request.get_json(silent=True)
    try:
        require_json_fields(
            payload,
            {"ejercicio_id", "orden", "series", "repeticiones", "peso_gramos", "descanso_segundos"},
            {"ejercicio_id", "orden", "series", "repeticiones", "descanso_segundos"},
        )
        exercise_id = positive_integer(payload["ejercicio_id"], "ejercicio_id")
        order = bounded_integer(payload["orden"], "orden", 1, 100)
        series = bounded_integer(payload["series"], "series", 1, 100)
        repetitions = bounded_integer(payload["repeticiones"], "repeticiones", 1, 1000)
        rest = bounded_integer(payload["descanso_segundos"], "descanso_segundos", 0, 3600)
        weight = payload.get("peso_gramos")
        if weight is not None:
            weight = bounded_integer(weight, "peso_gramos", 0, 2_000_000)
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    if connection.execute(
        "SELECT 1 FROM rutinas WHERE id_rutina = ? AND entrenador_id = ?",
        (routine_id, profile["id_entrenador"]),
    ).fetchone() is None:
        return jsonify({"error": "routine_not_found"}), 404
    try:
        cursor = connection.execute(
            """
            INSERT INTO rutina_ejercicio
                (rutina_id, ejercicio_id, orden, series, repeticiones,
                 peso_gramos, descanso_segundos)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (routine_id, exercise_id, order, series, repetitions, weight, rest),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "exercise_assignment_conflict"}), 409
    return jsonify({"routine_exercise": {"id": cursor.lastrowid}}), 201


@trainer_api_blueprint.post("/attendance")
@trainer_required
def record_attendance():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"inscripcion_id", "estado"}, {"inscripcion_id", "estado"})
        enrollment_id = positive_integer(payload["inscripcion_id"], "inscripcion_id")
        state = payload["estado"]
        if state not in {"presente", "ausente"}:
            raise ValueError("estado")
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    enrollment = connection.execute(
        """
        SELECT i.id_inscripcion, c.inicio_utc
        FROM inscripciones i
        JOIN clases c ON c.id_clase = i.clase_id
        WHERE i.id_inscripcion = ? AND i.estado = 'activa'
          AND c.entrenador_id = ?
        """,
        (enrollment_id, profile["id_entrenador"]),
    ).fetchone()
    if enrollment is None:
        return jsonify({"error": "enrollment_not_authorized"}), 404
    if enrollment["inicio_utc"] > utc_now():
        return jsonify({"error": "attendance_too_early"}), 409
    connection.execute(
        """
        INSERT INTO asistencias (inscripcion_id, fecha_utc, estado)
        VALUES (?, ?, ?)
        ON CONFLICT(inscripcion_id) DO UPDATE SET
            fecha_utc = excluded.fecha_utc, estado = excluded.estado
        """,
        (enrollment_id, utc_now(), state),
    )
    connection.commit()
    return jsonify({"attendance": {"enrollment_id": enrollment_id, "status": state}})


@trainer_api_blueprint.post("/availability")
@trainer_required
def create_availability():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"sede_id", "dia_semana", "hora_inicio", "hora_fin"}, {"sede_id", "dia_semana", "hora_inicio", "hora_fin"})
        site_id = positive_integer(payload["sede_id"], "sede_id")
        day = bounded_integer(payload["dia_semana"], "dia_semana", 1, 7)
        start = clean_text(payload["hora_inicio"], "hora_inicio", maximum=5)
        end = clean_text(payload["hora_fin"], "hora_fin", maximum=5)
        if not TIME_PATTERN.fullmatch(start) or not TIME_PATTERN.fullmatch(end) or end <= start:
            raise ValueError("horario")
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    if connection.execute(
        "SELECT 1 FROM entrenador_sede WHERE entrenador_id = ? AND sede_id = ? AND activo = 1",
        (profile["id_entrenador"], site_id),
    ).fetchone() is None:
        return jsonify({"error": "site_not_authorized"}), 403
    try:
        cursor = connection.execute(
            """
            INSERT INTO disponibilidad_entrenador
                (entrenador_id, sede_id, dia_semana, hora_inicio, hora_fin)
            VALUES (?, ?, ?, ?, ?)
            """,
            (profile["id_entrenador"], site_id, day, start, end),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "availability_conflict"}), 409
    return jsonify({"availability": {"id": cursor.lastrowid}}), 201


@trainer_api_blueprint.delete("/availability/<int:availability_id>")
@trainer_required
def delete_availability(availability_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    connection = get_db()
    cursor = connection.execute(
        "DELETE FROM disponibilidad_entrenador WHERE id_disponibilidad = ? AND entrenador_id = ?",
        (availability_id, profile["id_entrenador"]),
    )
    connection.commit()
    if cursor.rowcount != 1:
        return jsonify({"error": "availability_not_found"}), 404
    return jsonify({"deleted": True})
