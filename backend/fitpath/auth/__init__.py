"""Autenticación Google OIDC para el backend oficial de FitPath."""

from authlib.integrations.flask_client import OAuth
from flask import current_app


GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
GOOGLE_ISSUER = "https://accounts.google.com"


def init_auth(app):
    """Registra OIDC, autenticación y las vistas Cliente protegidas."""
    # La app factory crea un registro OAuth aislado y su propia caché.
    oauth = OAuth(app)
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url=GOOGLE_DISCOVERY_URL,
        client_kwargs={"scope": "openid email profile"},
    )
    oauth.register(
        name="google_calendar",
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url=GOOGLE_DISCOVERY_URL,
        client_kwargs={
            "scope": (
                "openid "
                "https://www.googleapis.com/auth/calendar.events.owned"
            )
        },
    )

    from .calendar_routes import calendar_auth_blueprint
    from .client_views import client_views_blueprint
    from .role_views import role_views_blueprint
    from .routes import auth_blueprint

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(calendar_auth_blueprint)
    app.register_blueprint(client_views_blueprint)
    app.register_blueprint(role_views_blueprint)


def get_oauth():
    """Devuelve el cliente OAuth de la app Flask activa."""
    return current_app.extensions["authlib.integrations.flask_client"]


__all__ = ["GOOGLE_DISCOVERY_URL", "GOOGLE_ISSUER", "get_oauth"]
