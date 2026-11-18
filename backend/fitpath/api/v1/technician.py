"""Mantenimiento limitado a la sede del Técnico autenticado."""

import sqlite3

from flask import Blueprint, current_app, jsonify, request

from ...auth.authorization import current_identity, require_api_access
from ...database import get_db
from ...permissions import TECHNICIAN_DATA_PERMISSION
from .role_utils import clean_text, csrf_is_valid, positive_integer, require_json_fields, utc_now


technician_api_blueprint = Blueprint(
    "technician_api", __name__, url_prefix="/api/v1/technician"
)
technician_required = require_api_access(
    roles=("Técnico de mantenimiento",), permission=TECHNICIAN_DATA_PERMISSION
)
MACHINE_STATES = {"operativa", "en_reparacion", "fuera_de_servicio"}
TICKET_STATES = {"abierto", "en_proceso", "resuelto", "cancelado"}


@technician_api_blueprint.after_request
def disable_private_cache(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _technician_profile():
    identity = current_identity()
    return get_db().execute(
        """
        SELECT t.id_tecnico, t.sede_id, s.nombre AS sede
        FROM tecnicos_mantenimiento t
        JOIN sedes s ON s.id_sede = t.sede_id
        WHERE t.usuario_id = ?
        """,
        (identity["user"]["id"],),
    ).fetchone()


def _profile_or_error():
    profile = _technician_profile()
    if profile is None:
        return None, (jsonify({"error": "technician_profile_required"}), 403)
    return profile, None


def _dashboard_payload(profile):
    connection = get_db()
    machines = [
        dict(row)
        for row in connection.execute(
            "SELECT id_maquina AS id, tipo, estado FROM maquinas WHERE sede_id = ? ORDER BY tipo, id_maquina",
            (profile["sede_id"],),
        ).fetchall()
    ]
    tickets = [
        dict(row)
        for row in connection.execute(
            """
            SELECT t.id_ticket AS id, t.maquina_id, m.tipo AS maquina,
                   t.fecha_generacion_utc, t.descripcion, t.estado
            FROM tickets_mantenimiento t
            JOIN maquinas m ON m.id_maquina = t.maquina_id
            WHERE t.tecnico_id = ? AND m.sede_id = ?
            ORDER BY t.fecha_generacion_utc DESC, t.id_ticket DESC
            """,
            (profile["id_tecnico"], profile["sede_id"]),
        ).fetchall()
    ]
    history = [
        dict(row)
        for row in connection.execute(
            """
            SELECT h.id_historial AS id, h.maquina_id, m.tipo AS maquina,
                   h.ticket_id, h.fecha_utc, h.estado_anterior,
                   h.estado_nuevo, h.descripcion
            FROM historial_mantenimiento h
            JOIN maquinas m ON m.id_maquina = h.maquina_id
            WHERE h.tecnico_id = ? AND m.sede_id = ?
            ORDER BY h.fecha_utc DESC, h.id_historial DESC LIMIT 100
            """,
            (profile["id_tecnico"], profile["sede_id"]),
        ).fetchall()
    ]
    return {
        "metrics": [
            {"label": "Máquinas asignadas", "value": len(machines)},
            {"label": "Tickets abiertos", "value": sum(ticket["estado"] in {"abierto", "en_proceso"} for ticket in tickets)},
            {"label": "Cambios registrados", "value": len(history)},
        ],
        "sections": [
            {"title": "Máquinas de la sede", "rows": machines},
            {"title": "Incidencias asignadas", "rows": tickets},
            {"title": "Historial de mantenimiento", "rows": history},
        ],
        "site": {"id": profile["sede_id"], "name": profile["sede"]},
        "options": {"machines": machines, "tickets": tickets},
    }


@technician_api_blueprint.get("/dashboard")
@technician_required
def technician_dashboard():
    profile, error = _profile_or_error()
    if error:
        return error
    return jsonify(_dashboard_payload(profile))


@technician_api_blueprint.post("/tickets")
@technician_required
def create_ticket():
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"maquina_id", "descripcion"}, {"maquina_id", "descripcion"})
        machine_id = positive_integer(payload["maquina_id"], "maquina_id")
        description = clean_text(payload["descripcion"], "descripcion", maximum=1000)
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    if connection.execute(
        "SELECT 1 FROM maquinas WHERE id_maquina = ? AND sede_id = ?",
        (machine_id, profile["sede_id"]),
    ).fetchone() is None:
        return jsonify({"error": "machine_not_authorized"}), 404
    try:
        cursor = connection.execute(
            """
            INSERT INTO tickets_mantenimiento
                (maquina_id, tecnico_id, fecha_generacion_utc, descripcion, estado)
            VALUES (?, ?, ?, ?, 'abierto')
            """,
            (machine_id, profile["id_tecnico"], utc_now(), description),
        )
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        current_app.logger.exception("No se pudo crear el ticket de mantenimiento.")
        return jsonify({"error": "ticket_create_failed"}), 500
    return jsonify({"ticket": {"id": cursor.lastrowid}}), 201


@technician_api_blueprint.patch("/tickets/<int:ticket_id>")
@technician_required
def update_ticket(ticket_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"estado"} or payload["estado"] not in TICKET_STATES:
        return jsonify({"error": "invalid_request"}), 400
    connection = get_db()
    cursor = connection.execute(
        """
        UPDATE tickets_mantenimiento SET estado = ?
        WHERE id_ticket = ? AND tecnico_id = ?
          AND EXISTS (
            SELECT 1 FROM maquinas m
            WHERE m.id_maquina = tickets_mantenimiento.maquina_id
              AND m.sede_id = ?
          )
        """,
        (payload["estado"], ticket_id, profile["id_tecnico"], profile["sede_id"]),
    )
    connection.commit()
    if cursor.rowcount != 1:
        return jsonify({"error": "ticket_not_found"}), 404
    return jsonify({"ticket": {"id": ticket_id, "status": payload["estado"]}})


@technician_api_blueprint.patch("/machines/<int:machine_id>")
@technician_required
def update_machine_state(machine_id):
    if not csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    profile, error = _profile_or_error()
    if error:
        return error
    payload = request.get_json(silent=True)
    try:
        require_json_fields(payload, {"estado", "descripcion", "ticket_id"}, {"estado"})
        state = payload["estado"]
        if state not in MACHINE_STATES:
            raise ValueError("estado")
        description = clean_text(payload.get("descripcion"), "descripcion", maximum=1000, optional=True)
        ticket_id = payload.get("ticket_id")
        if ticket_id is not None:
            ticket_id = positive_integer(ticket_id, "ticket_id")
    except ValueError as validation_error:
        return jsonify({"error": "invalid_request", "field": str(validation_error)}), 400
    connection = get_db()
    machine = connection.execute(
        "SELECT estado FROM maquinas WHERE id_maquina = ? AND sede_id = ?",
        (machine_id, profile["sede_id"]),
    ).fetchone()
    if machine is None:
        return jsonify({"error": "machine_not_authorized"}), 404
    if machine["estado"] == state:
        return jsonify({"error": "machine_state_unchanged"}), 409
    if ticket_id is not None and connection.execute(
        """
        SELECT 1 FROM tickets_mantenimiento
        WHERE id_ticket = ? AND maquina_id = ? AND tecnico_id = ?
        """,
        (ticket_id, machine_id, profile["id_tecnico"]),
    ).fetchone() is None:
        return jsonify({"error": "ticket_not_authorized"}), 404
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE maquinas SET estado = ? WHERE id_maquina = ? AND sede_id = ?",
            (state, machine_id, profile["sede_id"]),
        )
        history_id = connection.execute(
            """
            INSERT INTO historial_mantenimiento
                (maquina_id, ticket_id, tecnico_id, fecha_utc,
                 estado_anterior, estado_nuevo, descripcion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                machine_id,
                ticket_id,
                profile["id_tecnico"],
                utc_now(),
                machine["estado"],
                state,
                description,
            ),
        ).lastrowid
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        current_app.logger.exception("No se pudo actualizar el estado de la máquina.")
        return jsonify({"error": "machine_update_failed"}), 500
    return jsonify({"machine": {"id": machine_id, "status": state}, "history_id": history_id})
