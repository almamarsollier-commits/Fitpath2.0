"""Autorización incremental de Google Calendar, separada del login OIDC."""

import hmac
import secrets

from authlib.integrations.base_client.errors import OAuthError
from flask import Blueprint, current_app, redirect, session, url_for

from ..database import get_db
from ..permissions import CLIENT_DATA_PERMISSION
from ..services.google_calendar import (
    GOOGLE_CALENDAR_SCOPE,
    GoogleCalendarAuthorizationRequiredError,
    GoogleCalendarConfigurationError,
    GoogleCalendarSettings,
    granted_scopes,
    save_calendar_authorization,
)
from . import GOOGLE_ISSUER, get_oauth
from .authorization import current_identity, require_access


calendar_auth_blueprint = Blueprint(
    "calendar_auth", __name__, url_prefix="/auth/google/calendar"
)
calendar_access_required = require_access(
    roles=("Cliente",), permission=CLIENT_DATA_PERMISSION
)
CALENDAR_RESULT_URL = "/templates/cliente/clases/reservas.html"


def _result(state):
    return redirect(f"{CALENDAR_RESULT_URL}?calendar={state}")


def _log_failure(stage, error=None):
    error_name = type(error).__name__ if error is not None else "ValidationError"
    current_app.logger.warning(
        "Google Calendar OAuth rechazado: stage=%s error=%s",
        stage,
        error_name,
    )


def _settings():
    return GoogleCalendarSettings.from_mapping(current_app.config)


@calendar_auth_blueprint.get("/connect")
@calendar_access_required
def connect_google_calendar():
    try:
        _settings()
    except GoogleCalendarConfigurationError:
        return _result("configuration_required")

    identity = current_identity()
    linked = get_db().execute(
        """
        SELECT subject
        FROM identidades_google
        WHERE usuario_id = ? AND emisor = ?
        """,
        (identity["user"]["id"], GOOGLE_ISSUER),
    ).fetchone()
    if linked is None:
        return _result("identity_required")

    nonce = secrets.token_urlsafe(32)
    session["google_calendar_nonce"] = nonce
    session["google_calendar_user_id"] = identity["user"]["id"]
    redirect_uri = current_app.config.get(
        "GOOGLE_CALENDAR_REDIRECT_URI"
    ) or url_for("calendar_auth.google_calendar_callback", _external=True)
    try:
        client = get_oauth().create_client("google_calendar")
        return client.authorize_redirect(
            redirect_uri,
            nonce=nonce,
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            login_hint=linked["subject"],
        )
    except Exception as error:
        session.pop("google_calendar_nonce", None)
        session.pop("google_calendar_user_id", None)
        _log_failure("authorization_redirect", error)
        return _result("provider_unavailable")


@calendar_auth_blueprint.get("/callback")
@calendar_access_required
def google_calendar_callback():
    identity = current_identity()
    expected_nonce = session.pop("google_calendar_nonce", None)
    expected_user_id = session.pop("google_calendar_user_id", None)
    if (
        not expected_nonce
        or expected_user_id != identity["user"]["id"]
    ):
        _log_failure("session_state")
        return _result("authorization_error")

    stage = "token_exchange"
    try:
        token = get_oauth().create_client(
            "google_calendar"
        ).authorize_access_token()
        stage = "userinfo"
        userinfo = token.get("userinfo")
        if not isinstance(userinfo, dict):
            raise OAuthError("invalid_userinfo")
        stage = "nonce_claim"
        nonce = userinfo.get("nonce")
        if not isinstance(nonce, str) or not hmac.compare_digest(
            nonce, expected_nonce
        ):
            raise OAuthError("invalid_nonce")
        stage = "identity_claims"
        if userinfo.get("iss") != GOOGLE_ISSUER:
            raise OAuthError("invalid_issuer")
        linked = get_db().execute(
            """
            SELECT subject
            FROM identidades_google
            WHERE usuario_id = ? AND emisor = ?
            """,
            (identity["user"]["id"], GOOGLE_ISSUER),
        ).fetchone()
        subject = userinfo.get("sub")
        if (
            linked is None
            or not isinstance(subject, str)
            or not hmac.compare_digest(subject, linked["subject"])
        ):
            return _result("account_mismatch")
        stage = "granted_scopes"
        scopes = granted_scopes(token.get("scope"))
        if GOOGLE_CALENDAR_SCOPE not in scopes or "openid" not in scopes:
            raise GoogleCalendarAuthorizationRequiredError(
                "Google Calendar no fue autorizado."
            )
        stage = "token_storage"
        save_calendar_authorization(
            get_db(),
            identity["user"]["id"],
            token.get("refresh_token"),
            scopes,
            _settings(),
        )
    except Exception as error:
        _log_failure(stage, error)
        return _result(
            "authorization_denied"
            if getattr(error, "error", None) == "access_denied"
            else "authorization_error"
        )
    return _result("connected")
