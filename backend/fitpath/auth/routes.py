"""Rutas de inicio, callback, consulta mínima y cierre de sesión."""

import hmac
import secrets

from authlib.integrations.base_client.errors import OAuthError
from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, session, url_for

from ..database import get_db
from . import GOOGLE_ISSUER, get_oauth
from .authorization import current_identity
from .identities import create_link_request, find_active_user


auth_blueprint = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth",
    template_folder="templates",
    static_folder="../../../statics",
    static_url_path="/static",
)

ROLE_HOME_ENDPOINTS = {
    "Cliente": "client_views.client_home",
    "Entrenador": "role_views.trainer_home",
    "Jefe de sede": "role_views.manager_home",
    "Administrador": "role_views.admin_home",
    "Técnico de mantenimiento": "role_views.technician_home",
}


def _home_url(identity):
    if not identity:
        return None
    endpoint = ROLE_HOME_ENDPOINTS.get(identity["user"]["rol"])
    return url_for(endpoint) if endpoint else None


def _current_fitpath_identity():
    """Compatibilidad interna para las vistas y pruebas existentes."""
    return current_identity()


def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


def _log_google_callback_failure(stage, error=None):
    """Registra sólo la etapa y el tipo; nunca datos de la respuesta OAuth."""
    error_name = type(error).__name__ if error is not None else "ValidationError"
    oauth_code = getattr(error, "error", None)
    if not (
        isinstance(oauth_code, str)
        and len(oauth_code) <= 64
        and oauth_code.replace("_", "").isalnum()
    ):
        oauth_code = "unavailable"
    current_app.logger.warning(
        "Google OAuth callback rechazado: stage=%s error=%s oauth_code=%s",
        stage,
        error_name,
        oauth_code,
    )


def _configured():
    return bool(
        current_app.config.get("GOOGLE_CLIENT_ID")
        and current_app.config.get("GOOGLE_CLIENT_SECRET")
        and current_app.config.get("SECRET_KEY")
    )


@auth_blueprint.get("/login")
def login_page():
    return _no_store(
        current_app.make_response(
            render_template(
                "auth/login.html",
                error=request.args.get("error"),
                auth_identity=_current_fitpath_identity(),
                dashboard_url=_home_url(_current_fitpath_identity()),
                demo_login_enabled=current_app.config.get("DEMO_LOGIN_ENABLED", False),
                logout_success=request.args.get("logout") == "1",
            )
        )
    )


@auth_blueprint.post("/demo-login/<role_slug>")
def demo_login(role_slug):
    if not current_app.config.get("DEMO_LOGIN_ENABLED"):
        abort(404)
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        abort(404)
    from ..demo_data import DEMO_USERS

    demo = DEMO_USERS.get(role_slug)
    if demo is None:
        abort(404)
    role, username, _email = demo
    user = get_db().execute(
        """
        SELECT u.id_usuario, r.nombre AS rol
        FROM usuarios u JOIN roles r ON r.id_rol = u.rol_id
        WHERE u.nombre_usuario = ? AND u.activo = 1 AND r.nombre = ?
        """,
        (username, role),
    ).fetchone()
    if user is None:
        return render_template("auth/login.html", error="demo_unavailable"), 503
    endpoint = ROLE_HOME_ENDPOINTS.get(user["rol"])
    if endpoint is None:
        abort(403)
    session.clear()
    session.permanent = True
    session["fitpath_user_id"] = user["id_usuario"]
    session["csrf_token"] = secrets.token_urlsafe(32)
    return redirect(url_for(endpoint))


@auth_blueprint.get("/google/login")
def google_login():
    if not _configured():
        return render_template("auth/login.html", error="auth_unavailable"), 503

    nonce = secrets.token_urlsafe(32)
    session["google_oidc_nonce"] = nonce
    redirect_uri = current_app.config.get("GOOGLE_REDIRECT_URI") or url_for(
        "auth.google_callback", _external=True
    )
    try:
        client = get_oauth().create_client("google")
        return client.authorize_redirect(redirect_uri, nonce=nonce)
    except Exception:
        session.pop("google_oidc_nonce", None)
        return render_template("auth/login.html", error="provider_unavailable"), 503


@auth_blueprint.get("/google/callback")
def google_callback():
    if not _configured():
        return render_template("auth/login.html", error="auth_unavailable"), 503

    expected_nonce = session.pop("google_oidc_nonce", None)
    if not expected_nonce:
        _log_google_callback_failure("session_nonce")
        return render_template("auth/login.html", error="login_failed"), 400

    stage = "token_exchange_or_oidc_validation"
    try:
        token = get_oauth().create_client("google").authorize_access_token()
        stage = "userinfo"
        userinfo = token.get("userinfo")
        if not isinstance(userinfo, dict):
            raise OAuthError("invalid_userinfo")
        # Authlib valida firma, issuer, audiencia, expiración y el nonce enviado.
        # Se compara también el nonce de la sesión para exigir el flujo iniciado aquí.
        stage = "nonce_claim"
        nonce = userinfo.get("nonce")
        if not isinstance(nonce, str) or not hmac.compare_digest(nonce, expected_nonce):
            raise OAuthError("invalid_nonce")
        stage = "identity_claims"
        issuer = userinfo.get("iss")
        subject = userinfo.get("sub")
        if issuer != GOOGLE_ISSUER or not isinstance(subject, str) or not subject.strip():
            raise OAuthError("invalid_identity")
    except Exception as error:
        _log_google_callback_failure(stage, error)
        return render_template("auth/login.html", error="login_failed"), 400

    connection = get_db()
    user = find_active_user(connection, issuer, subject)
    if user is None:
        linked_anywhere = connection.execute(
            "SELECT 1 FROM identidades_google WHERE emisor = ? AND subject = ?",
            (issuer, subject),
        ).fetchone()
        if linked_anywhere:
            return render_template("auth/login.html", error="account_inactive"), 403
        reference, expires = create_link_request(connection, issuer, subject)
        return render_template(
            "auth/link_request.html", reference=reference, expires=expires
        ), 403

    # Flask usa sesiones firmadas en cookie: limpiar el estado previo rota
    # lógicamente la sesión y evita conservar datos preautenticación.
    session.clear()
    session.permanent = True
    session["fitpath_user_id"] = user["id_usuario"]
    session["csrf_token"] = secrets.token_urlsafe(32)
    endpoint = ROLE_HOME_ENDPOINTS.get(user["rol"])
    if endpoint is None:
        session.clear()
        return render_template("auth/login.html", error="role_unavailable"), 403
    return redirect(url_for(endpoint))


@auth_blueprint.get("/me")
def identity():
    auth_identity = _current_fitpath_identity()
    if auth_identity is None:
        response, status = jsonify({"authenticated": False}), 401
        return _no_store(response), status

    return _no_store(jsonify(auth_identity))


@auth_blueprint.post("/logout")
def logout():
    supplied = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not supplied or not expected or not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "csrf_failed"}), 400
    session.clear()
    return redirect(url_for("auth.login_page", logout="1"))
