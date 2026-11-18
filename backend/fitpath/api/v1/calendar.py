"""Estado y creación explícita de eventos Calendar para el Cliente."""

import hmac

from flask import Blueprint, current_app, jsonify, request

from ...auth.authorization import current_identity, require_api_access
from ...database import get_db
from ...permissions import CLIENT_DATA_PERMISSION
from ...services.google_calendar import (
    GoogleCalendarAuthorizationRequiredError,
    GoogleCalendarConfigurationError,
    GoogleCalendarEnrollmentNotFoundError,
    GoogleCalendarError,
    GoogleCalendarPermissionError,
    GoogleCalendarProviderError,
    GoogleCalendarSettings,
    calendar_connection_status,
    create_enrollment_calendar_event,
)


calendar_api_blueprint = Blueprint(
    "calendar_api", __name__, url_prefix="/api/v1/client/calendar"
)
calendar_access_required = require_api_access(
    roles=("Cliente",), permission=CLIENT_DATA_PERMISSION
)


@calendar_api_blueprint.after_request
def disable_private_cache(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _csrf_is_valid():
    identity = current_identity()
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = identity["csrf_token"] if identity else ""
    return bool(
        supplied and expected and hmac.compare_digest(supplied, expected)
    )


def _client_id(user_id):
    row = get_db().execute(
        "SELECT id_cliente FROM clientes WHERE usuario_id = ?", (user_id,)
    ).fetchone()
    return row["id_cliente"] if row else None


@calendar_api_blueprint.get("/status")
@calendar_access_required
def google_calendar_status():
    identity = current_identity()
    try:
        settings = GoogleCalendarSettings.from_mapping(current_app.config)
    except GoogleCalendarConfigurationError:
        return jsonify(
            {
                "configured": False,
                "connected": False,
                "state": "configuration_required",
            }
        )
    return jsonify(
        calendar_connection_status(
            get_db(), identity["user"]["id"], settings
        )
    )


@calendar_api_blueprint.post("/enrollments/<int:enrollment_id>/event")
@calendar_access_required
def add_enrollment_to_google_calendar(enrollment_id):
    if not _csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400
    identity = current_identity()
    user_id = identity["user"]["id"]
    client_id = _client_id(user_id)
    if client_id is None:
        return jsonify({"error": "client_profile_required"}), 403
    try:
        settings = GoogleCalendarSettings.from_mapping(current_app.config)
        event = create_enrollment_calendar_event(
            get_db(), user_id, client_id, enrollment_id, settings
        )
        return jsonify({"event": event}), 201 if event["created"] else 200
    except GoogleCalendarConfigurationError:
        return jsonify({"error": "calendar_not_configured"}), 503
    except GoogleCalendarAuthorizationRequiredError:
        return jsonify({"error": "calendar_authorization_required"}), 409
    except GoogleCalendarEnrollmentNotFoundError:
        return jsonify({"error": "enrollment_not_available"}), 404
    except GoogleCalendarPermissionError:
        get_db().execute(
            "DELETE FROM autorizaciones_google_calendar WHERE usuario_id = ?",
            (user_id,),
        )
        get_db().commit()
        return jsonify({"error": "calendar_authorization_expired"}), 409
    except GoogleCalendarProviderError:
        return jsonify({"error": "calendar_provider_unavailable"}), 502
    except GoogleCalendarError:
        current_app.logger.exception(
            "No se pudo registrar el evento de Google Calendar."
        )
        return jsonify({"error": "calendar_event_failed"}), 500
