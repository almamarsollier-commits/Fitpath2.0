"""Rutas de inicio, callback, consulta mínima y cierre de sesión."""

import hmac
import secrets

from authlib.integrations.base_client.errors import OAuthError
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

from ..database import get_db
from . import GOOGLE_ISSUER, get_oauth
from .identities import create_link_request, find_active_user


auth_blueprint = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth",
    template_folder="templates",
    static_folder="../../../statics",
    static_url_path="/static",
)


def _current_fitpath_identity():
    """Resuelve el usuario y rol desde SQLite para la sesión Flask actual."""
    user_id = session.get("fitpath_user_id")
    csrf_token = session.get("csrf_token")
    if not user_id or not csrf_token:
        return None

    user = get_db().execute(
        """
        SELECT u.id_usuario, u.nombre, u.apellido, u.rol_id, r.nombre AS rol
        FROM usuarios AS u
        JOIN roles AS r ON r.id_rol = u.rol_id
        WHERE u.id_usuario = ? AND u.activo = 1
        """,
        (user_id,),
    ).fetchone()
    if user is None:
        session.clear()
        return None

    return {
        "authenticated": True,
        "csrf_token": csrf_token,
        "user": {
            "id": user["id_usuario"],
            "nombre": user["nombre"],
            "apellido": user["apellido"],
            "rol": user["rol"],
        },
    }


def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


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
                logout_success=request.args.get("logout") == "1",
            )
        )
    )


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
        return render_template("auth/login.html", error="login_failed"), 400

    try:
        token = get_oauth().create_client("google").authorize_access_token()
        userinfo = token.get("userinfo")
        if not isinstance(userinfo, dict):
            raise OAuthError("invalid_userinfo")
        # Authlib valida firma, issuer, audiencia, expiración y el nonce enviado.
        # Se compara también el nonce de la sesión para exigir el flujo iniciado aquí.
        nonce = userinfo.get("nonce")
        if not isinstance(nonce, str) or not hmac.compare_digest(nonce, expected_nonce):
            raise OAuthError("invalid_nonce")
        issuer = userinfo.get("iss")
        subject = userinfo.get("sub")
        if issuer != GOOGLE_ISSUER or not isinstance(subject, str) or not subject.strip():
            raise OAuthError("invalid_identity")
    except Exception:
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
    return redirect(url_for("client_views.client_home"))


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
