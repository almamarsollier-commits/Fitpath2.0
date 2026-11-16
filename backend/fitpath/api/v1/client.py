"""Operaciones reales y propias del espacio Cliente."""

import hmac
import sqlite3
import unicodedata
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from ...auth.authorization import current_identity, require_api_access
from ...database import get_db
from ...permissions import CLIENT_DATA_PERMISSION
from ...services.enrollments import (
    ActiveEnrollmentNotFoundError,
    ClassFullError,
    ClassNotFoundError,
    ClassUnavailableError,
    DuplicateActiveEnrollmentError,
    EnrollmentCancellationError,
    EnrollmentError,
    EnrollmentRequestError,
    cancel_enrollment,
    create_enrollment,
)


client_api_blueprint = Blueprint("client_api", __name__, url_prefix="/api/v1/client")
client_required = require_api_access(
    roles=("Cliente",), permission=CLIENT_DATA_PERMISSION
)


@client_api_blueprint.after_request
def disable_private_cache(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _client_id():
    identity = current_identity()
    row = get_db().execute(
        "SELECT id_cliente FROM clientes WHERE usuario_id = ?",
        (identity["user"]["id"],),
    ).fetchone()
    return row["id_cliente"] if row else None


def _csrf_is_valid():
    identity = current_identity()
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = identity["csrf_token"] if identity else ""
    return bool(supplied and expected and hmac.compare_digest(supplied, expected))


def _now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _positive_id(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _client_or_error():
    client_id = _client_id()
    if client_id is None:
        return None, (jsonify({"error": "client_profile_required"}), 403)
    return client_id, None


def _classes_payload(client_id):
    rows = get_db().execute(
        """
        SELECT
            c.id_clase AS id, a.nombre AS actividad, s.nombre AS sede,
            s.direccion, s.zona_horaria, c.inicio_utc, c.fin_utc,
            c.cupo_maximo, c.estado,
            (SELECT count(*) FROM inscripciones AS occupied
             WHERE occupied.clase_id = c.id_clase AND occupied.estado = 'activa')
                AS inscriptos,
            (SELECT own.id_inscripcion FROM inscripciones AS own
             WHERE own.clase_id = c.id_clase AND own.cliente_id = ?
               AND own.estado = 'activa'
             LIMIT 1) AS inscripcion_id
        FROM clases AS c
        JOIN actividades AS a ON a.id_actividad = c.actividad_id
        JOIN sedes AS s ON s.id_sede = c.sede_id
        WHERE c.inicio_utc > ?
        ORDER BY c.inicio_utc, c.id_clase
        LIMIT 100
        """,
        (client_id, _now_utc()),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "actividad": row["actividad"],
            "sede": row["sede"],
            "direccion": row["direccion"],
            "zona_horaria": row["zona_horaria"],
            "inicio_utc": row["inicio_utc"],
            "fin_utc": row["fin_utc"],
            "estado": row["estado"],
            "cupo_maximo": row["cupo_maximo"],
            "inscriptos": row["inscriptos"],
            "cupos_disponibles": max(0, row["cupo_maximo"] - row["inscriptos"]),
            "inscripto": row["inscripcion_id"] is not None,
            "inscripcion_id": row["inscripcion_id"],
        }
        for row in rows
    ]


@client_api_blueprint.get("/classes")
@client_required
def get_client_classes():
    client_id, error = _client_or_error()
    if error:
        return error
    return jsonify({"classes": _classes_payload(client_id)})


@client_api_blueprint.post("/classes/<int:class_id>/enrollment")
@client_required
def enroll_in_class(class_id):
    if not _csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    client_id, error = _client_or_error()
    if error:
        return error
    try:
        enrollment_id = create_enrollment(get_db(), client_id, class_id)
        return jsonify({"enrollment": {"id": enrollment_id, "class_id": class_id}}), 201
    except ClassNotFoundError:
        return jsonify({"error": "class_not_found"}), 404
    except DuplicateActiveEnrollmentError:
        return jsonify({"error": "already_enrolled"}), 409
    except ClassFullError:
        return jsonify({"error": "class_full"}), 409
    except ClassUnavailableError:
        return jsonify({"error": "class_unavailable"}), 409
    except EnrollmentRequestError:
        return jsonify({"error": "invalid_request"}), 400
    except EnrollmentError:
        current_app.logger.exception("No se pudo crear la inscripción del Cliente.")
        return jsonify({"error": "enrollment_failed"}), 500


@client_api_blueprint.delete("/classes/<int:class_id>/enrollment")
@client_required
def cancel_client_enrollment(class_id):
    if not _csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    client_id, error = _client_or_error()
    if error:
        return error
    try:
        enrollment_id = cancel_enrollment(get_db(), client_id, class_id)
        return jsonify(
            {"enrollment": {"id": enrollment_id, "class_id": class_id, "status": "cancelada"}}
        )
    except ActiveEnrollmentNotFoundError:
        return jsonify({"error": "active_enrollment_not_found"}), 404
    except EnrollmentCancellationError:
        return jsonify({"error": "enrollment_not_cancellable"}), 409
    except EnrollmentError:
        current_app.logger.exception("No se pudo cancelar la inscripción del Cliente.")
        return jsonify({"error": "enrollment_cancellation_failed"}), 500


@client_api_blueprint.get("/enrollments")
@client_required
def get_client_enrollments():
    client_id, error = _client_or_error()
    if error:
        return error
    rows = get_db().execute(
        """
        SELECT i.id_inscripcion AS id, i.estado, i.fecha_utc,
               c.id_clase, c.inicio_utc, c.fin_utc, c.estado AS clase_estado,
               a.nombre AS actividad, s.nombre AS sede,
               ast.estado AS asistencia
        FROM inscripciones AS i
        JOIN clases AS c ON c.id_clase = i.clase_id
        JOIN actividades AS a ON a.id_actividad = c.actividad_id
        JOIN sedes AS s ON s.id_sede = c.sede_id
        LEFT JOIN asistencias AS ast ON ast.inscripcion_id = i.id_inscripcion
        WHERE i.cliente_id = ?
        ORDER BY c.inicio_utc DESC, i.id_inscripcion DESC
        LIMIT 100
        """,
        (client_id,),
    ).fetchall()
    return jsonify({"enrollments": [dict(row) for row in rows]})


@client_api_blueprint.get("/routines")
@client_required
def get_client_routines():
    client_id, error = _client_or_error()
    if error:
        return error
    connection = get_db()
    routines = connection.execute(
        """
        SELECT r.id_rutina AS id, r.nombre, r.descripcion, r.fecha_creacion_utc,
               r.observaciones_entrenador, o.nombre AS objetivo
        FROM rutinas AS r
        LEFT JOIN objetivos AS o ON o.id_objetivo = r.objetivo_id
        WHERE r.cliente_id = ?
        ORDER BY r.fecha_creacion_utc DESC, r.id_rutina DESC
        """,
        (client_id,),
    ).fetchall()
    payload = []
    for routine in routines:
        item = dict(routine)
        item["ejercicios"] = [
            dict(row)
            for row in connection.execute(
                """
                SELECT e.id_ejercicio AS id, e.nombre, e.grupo_muscular,
                       e.descripcion, re.orden, re.series, re.repeticiones,
                       re.peso_gramos, re.descanso_segundos
                FROM rutina_ejercicio AS re
                JOIN ejercicios AS e ON e.id_ejercicio = re.ejercicio_id
                WHERE re.rutina_id = ?
                ORDER BY re.orden, re.id_rutina_ejercicio
                """,
                (routine["id"],),
            ).fetchall()
        ]
        payload.append(item)
    return jsonify({"routines": payload})


@client_api_blueprint.get("/progress")
@client_required
def get_client_progress():
    client_id, error = _client_or_error()
    if error:
        return error
    rows = get_db().execute(
        """
        SELECT id_progreso AS id, fecha_utc, peso_kg, porcentaje_grasa,
               rendimiento_ejercicios, observaciones
        FROM progresos
        WHERE cliente_id = ?
        ORDER BY fecha_utc DESC, id_progreso DESC
        LIMIT 100
        """,
        (client_id,),
    ).fetchall()
    return jsonify({"progress": [dict(row) for row in rows]})


def _optional_number(value, field, minimum, maximum):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(field)
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(field) from error
    if not minimum <= number <= maximum:
        raise ValueError(field)
    return round(number, 2)


def _optional_text(value, field, maximum):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(field)
    cleaned = unicodedata.normalize("NFC", value).strip()
    if not cleaned or len(cleaned) > maximum or any(
        unicodedata.category(character).startswith("C") for character in cleaned
    ):
        raise ValueError(field)
    return cleaned


@client_api_blueprint.post("/progress")
@client_required
def create_client_progress():
    if not _csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    client_id, error = _client_or_error()
    if error:
        return error
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) - {
        "peso_kg", "porcentaje_grasa", "rendimiento_ejercicios", "observaciones"
    }:
        return jsonify({"error": "invalid_request"}), 400
    try:
        values = {
            "peso_kg": _optional_number(payload.get("peso_kg"), "peso_kg", 20, 400),
            "porcentaje_grasa": _optional_number(
                payload.get("porcentaje_grasa"), "porcentaje_grasa", 0, 100
            ),
            "rendimiento_ejercicios": _optional_text(
                payload.get("rendimiento_ejercicios"), "rendimiento_ejercicios", 1000
            ),
            "observaciones": _optional_text(
                payload.get("observaciones"), "observaciones", 1000
            ),
        }
    except ValueError as validation_error:
        return jsonify({"error": "invalid_progress", "field": str(validation_error)}), 400
    if all(value is None for value in values.values()):
        return jsonify({"error": "progress_value_required"}), 400
    connection = get_db()
    try:
        cursor = connection.execute(
            """
            INSERT INTO progresos
                (cliente_id, fecha_utc, peso_kg, porcentaje_grasa,
                 rendimiento_ejercicios, observaciones)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (client_id, _now_utc(), *values.values()),
        )
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        current_app.logger.exception("No se pudo registrar el progreso del Cliente.")
        return jsonify({"error": "progress_create_failed"}), 500
    row = connection.execute(
        """
        SELECT id_progreso AS id, fecha_utc, peso_kg, porcentaje_grasa,
               rendimiento_ejercicios, observaciones
        FROM progresos WHERE id_progreso = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()
    return jsonify({"progress": dict(row)}), 201


@client_api_blueprint.get("/dashboard")
@client_required
def get_client_dashboard():
    client_id, error = _client_or_error()
    if error:
        return error
    connection = get_db()
    next_class = connection.execute(
        """
        SELECT c.id_clase AS id, a.nombre AS actividad, s.nombre AS sede,
               c.inicio_utc, c.fin_utc
        FROM inscripciones AS i
        JOIN clases AS c ON c.id_clase = i.clase_id
        JOIN actividades AS a ON a.id_actividad = c.actividad_id
        JOIN sedes AS s ON s.id_sede = c.sede_id
        WHERE i.cliente_id = ? AND i.estado = 'activa'
          AND c.estado = 'programada' AND c.inicio_utc > ?
        ORDER BY c.inicio_utc LIMIT 1
        """,
        (client_id, _now_utc()),
    ).fetchone()
    counts = connection.execute(
        """
        SELECT
          (SELECT count(*) FROM inscripciones WHERE cliente_id = ? AND estado = 'activa') AS inscripciones,
          (SELECT count(*) FROM rutinas WHERE cliente_id = ?) AS rutinas,
          (SELECT count(*) FROM progresos WHERE cliente_id = ?) AS progresos
        """,
        (client_id, client_id, client_id),
    ).fetchone()
    return jsonify(
        {
            "next_class": dict(next_class) if next_class else None,
            "counts": dict(counts),
        }
    )
