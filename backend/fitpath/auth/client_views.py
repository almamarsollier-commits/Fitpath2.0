"""Vistas demostrativas Cliente servidas detrás de la sesión FitPath."""

from pathlib import Path

from flask import Blueprint, abort, redirect, send_from_directory, url_for

from .routes import _current_fitpath_identity


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLIENT_TEMPLATES = PROJECT_ROOT / "templates" / "cliente"
PUBLIC_TEMPLATES = PROJECT_ROOT / "templates"
PUBLIC_STATICS = PROJECT_ROOT / "statics"

CLIENT_VIEW_PATHS = (
    "inicio/resumen.html",
    "inicio/actividad.html",
    "inicio/proxima-clase.html",
    "clases/index.html",
    "clases/detalle.html",
    "clases/reservas.html",
    "rutina/semana.html",
    "rutina/entrenamiento.html",
    "rutina/ejercicio.html",
    "progreso/index.html",
    "progreso/evolucion.html",
    "perfil/index.html",
    "perfil/membresia.html",
)

client_views_blueprint = Blueprint("client_views", __name__)


def _send_client_view(filename):
    if filename not in CLIENT_VIEW_PATHS:
        abort(404)

    identity = _current_fitpath_identity()
    if identity is None:
        return redirect(url_for("auth.login_page"))
    if identity["user"]["rol"] != "Cliente":
        abort(403)

    response = send_from_directory(CLIENT_TEMPLATES, filename)
    response.headers["Cache-Control"] = "private, no-store"
    return response


@client_views_blueprint.get("/auth/cliente")
def client_home():
    return _send_client_view("inicio/resumen.html")


@client_views_blueprint.get("/templates/cliente/<path:filename>")
def client_view(filename):
    return _send_client_view(filename)


@client_views_blueprint.get("/templates/landing.html")
def public_landing():
    response = send_from_directory(PUBLIC_TEMPLATES, "landing.html")
    response.headers["Cache-Control"] = "no-cache"
    return response


@client_views_blueprint.get("/statics/<path:filename>")
def public_static(filename):
    response = send_from_directory(PUBLIC_STATICS, filename)
    response.headers["Cache-Control"] = "no-cache"
    return response
