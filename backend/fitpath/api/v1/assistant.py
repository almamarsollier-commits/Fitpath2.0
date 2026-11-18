"""Lecturas reales y autorizadas para FitPath Smart Assistant."""

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from ...auth.authorization import current_identity, require_api_access
from ...database import get_db
from ...permissions import CLIENT_DATA_PERMISSION
from ...services.enrollments import (
    ActiveEnrollmentNotFoundError,
    ActiveMembershipRequiredError,
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
from .role_utils import csrf_is_valid, positive_integer, require_json_fields


assistant_api_blueprint = Blueprint(
    "assistant_api", __name__, url_prefix="/api/v1/assistant"
)
client_read_required = require_api_access(
    roles=("Cliente",), permission=CLIENT_DATA_PERMISSION
)


@assistant_api_blueprint.after_request
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


def _client_profile_error():
    return jsonify({"error": "client_profile_required"}), 403


@assistant_api_blueprint.get("/capabilities")
@client_read_required
def capabilities():
    return jsonify(
        {
            "read": [
                "classes.list",
                "routine.get",
                "progress.get",
                "membership.get",
            ],
            "write": ["enrollments.create", "enrollments.cancel"],
            "disabled": [],
            "reason": None,
        }
    )


@assistant_api_blueprint.get("/classes")
@client_read_required
def classes():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now[:10]
    client_id = _client_id()
    if client_id is None:
        return _client_profile_error()
    connection = get_db()
    has_active_membership = connection.execute(
        """
        SELECT 1
        FROM cliente_membresia
        WHERE cliente_id = ? AND estado = 'activa'
          AND fecha_inicio <= ?
          AND (fecha_fin IS NULL OR fecha_fin >= ?)
        """,
        (client_id, today, today),
    ).fetchone() is not None
    rows = connection.execute(
        """
        SELECT
            c.id_clase,
            a.nombre AS actividad,
            s.nombre AS sede,
            c.inicio_utc,
            c.fin_utc,
            c.cupo_maximo,
            c.cupo_maximo - SUM(CASE WHEN i.estado = 'activa' THEN 1 ELSE 0 END)
                AS cupos_disponibles,
            EXISTS (
                SELECT 1 FROM inscripciones AS own
                WHERE own.clase_id = c.id_clase
                  AND own.cliente_id = ? AND own.estado = 'activa'
            ) AS inscripto
        FROM clases AS c
        JOIN actividades AS a ON a.id_actividad = c.actividad_id
        JOIN sedes AS s ON s.id_sede = c.sede_id
        LEFT JOIN inscripciones AS i ON i.clase_id = c.id_clase
        WHERE c.estado = 'programada' AND c.inicio_utc > ?
        GROUP BY c.id_clase
        ORDER BY c.inicio_utc, c.id_clase
        LIMIT 20
        """,
        (client_id, now),
    ).fetchall()
    return jsonify(
        {
            "classes": [
                {
                    "id": row["id_clase"],
                    "activity": row["actividad"],
                    "site": row["sede"],
                    "starts_at": row["inicio_utc"],
                    "ends_at": row["fin_utc"],
                    "capacity": row["cupo_maximo"],
                    "available_spots": max(0, row["cupos_disponibles"]),
                    "enrollment_available": bool(
                        has_active_membership
                        and not row["inscripto"]
                        and row["cupos_disponibles"] > 0
                    ),
                    "enrolled": bool(row["inscripto"]),
                }
                for row in rows
            ]
        }
    )


@assistant_api_blueprint.post("/enrollments")
@client_read_required
def create_assistant_enrollment():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    client_id = _client_id()
    if client_id is None:
        return _client_profile_error()
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"clase_id"}, {"clase_id"})
        class_id = positive_integer(payload["clase_id"], "clase_id")
        enrollment_id = create_enrollment(get_db(), client_id, class_id)
    except ValueError:
        return jsonify({"error": "invalid_request"}), 400
    except EnrollmentRequestError:
        return jsonify({"error": "invalid_request"}), 400
    except ClassNotFoundError:
        return jsonify({"error": "class_not_found"}), 404
    except DuplicateActiveEnrollmentError:
        return jsonify({"error": "already_enrolled"}), 409
    except ActiveMembershipRequiredError:
        return jsonify({"error": "active_membership_required"}), 409
    except ClassFullError:
        return jsonify({"error": "class_full"}), 409
    except ClassUnavailableError:
        return jsonify({"error": "class_unavailable"}), 409
    except EnrollmentError:
        current_app.logger.exception("El asistente no pudo crear la inscripción.")
        return jsonify({"error": "enrollment_failed"}), 500
    return jsonify(
        {
            "enrollment": {"id": enrollment_id, "class_id": class_id},
            "message": f"Tu inscripción a la clase {class_id} quedó confirmada.",
        }
    ), 201


@assistant_api_blueprint.delete("/enrollments/<int:class_id>")
@client_read_required
def cancel_assistant_enrollment(class_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    client_id = _client_id()
    if client_id is None:
        return _client_profile_error()
    try:
        enrollment_id = cancel_enrollment(get_db(), client_id, class_id)
    except ActiveEnrollmentNotFoundError:
        return jsonify({"error": "active_enrollment_not_found"}), 404
    except EnrollmentCancellationError:
        return jsonify({"error": "enrollment_not_cancellable"}), 409
    except EnrollmentError:
        current_app.logger.exception("El asistente no pudo cancelar la inscripción.")
        return jsonify({"error": "enrollment_cancellation_failed"}), 500
    return jsonify(
        {
            "enrollment": {
                "id": enrollment_id,
                "class_id": class_id,
                "status": "cancelada",
            },
            "message": f"La inscripción a la clase {class_id} quedó cancelada.",
        }
    )


@assistant_api_blueprint.get("/routine")
@client_read_required
def routine():
    client_id = _client_id()
    if client_id is None:
        return _client_profile_error()
    row = get_db().execute(
        """
        SELECT r.id_rutina, r.nombre, r.fecha_creacion_utc, COUNT(re.id_rutina_ejercicio)
            AS cantidad_ejercicios
        FROM rutinas AS r
        LEFT JOIN rutina_ejercicio AS re ON re.rutina_id = r.id_rutina
        WHERE r.cliente_id = ? AND r.activa = 1
        GROUP BY r.id_rutina
        ORDER BY r.fecha_creacion_utc DESC, r.id_rutina DESC
        LIMIT 1
        """,
        (client_id,),
    ).fetchone()
    if row is None:
        return jsonify({"routine": None, "message": "No tenés una rutina registrada todavía."})
    return jsonify(
        {
            "routine": {
                "id": row["id_rutina"],
                "name": row["nombre"],
                "created_at": row["fecha_creacion_utc"],
                "exercise_count": row["cantidad_ejercicios"],
            }
        }
    )


@assistant_api_blueprint.get("/progress")
@client_read_required
def progress():
    client_id = _client_id()
    if client_id is None:
        return _client_profile_error()
    row = get_db().execute(
        """
        SELECT id_progreso, fecha_utc, peso_kg, porcentaje_grasa
        FROM progresos
        WHERE cliente_id = ?
        ORDER BY fecha_utc DESC, id_progreso DESC
        LIMIT 1
        """,
        (client_id,),
    ).fetchone()
    if row is None:
        return jsonify({"progress": None, "message": "No tenés progreso registrado todavía."})
    return jsonify(
        {
            "progress": {
                "id": row["id_progreso"],
                "recorded_at": row["fecha_utc"],
                "weight_kg": row["peso_kg"],
                "body_fat_percentage": row["porcentaje_grasa"],
            }
        }
    )


@assistant_api_blueprint.get("/membership")
@client_read_required
def membership():
    client_id = _client_id()
    if client_id is None:
        return _client_profile_error()
    row = get_db().execute(
        """
        SELECT cm.id_cliente_membresia, m.nombre, cm.estado, cm.fecha_inicio, cm.fecha_fin
        FROM cliente_membresia AS cm
        JOIN membresias AS m ON m.id_membresia = cm.membresia_id
        WHERE cm.cliente_id = ? AND cm.estado = 'activa'
        ORDER BY cm.fecha_inicio DESC, cm.id_cliente_membresia DESC
        LIMIT 1
        """,
        (client_id,),
    ).fetchone()
    if row is None:
        return jsonify({"membership": None, "message": "No tenés una membresía activa registrada."})
    return jsonify(
        {
            "membership": {
                "id": row["id_cliente_membresia"],
                "name": row["nombre"],
                "status": row["estado"],
                "starts_on": row["fecha_inicio"],
                "ends_on": row["fecha_fin"],
            }
        }
    )
