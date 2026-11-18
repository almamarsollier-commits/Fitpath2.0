"""Dashboards protegidos para los roles internos de FitPath."""

from flask import Blueprint, render_template, url_for

from ..permissions import (
    ADMIN_VIEWS_PERMISSION,
    MANAGER_VIEWS_PERMISSION,
    TECHNICIAN_VIEWS_PERMISSION,
    TRAINER_VIEWS_PERMISSION,
)
from .authorization import current_identity, require_access


role_views_blueprint = Blueprint(
    "role_views", __name__, template_folder="templates"
)
ALL_ROLES = (
    "Cliente",
    "Entrenador",
    "Jefe de sede",
    "Administrador",
    "Técnico de mantenimiento",
)
ROLE_HOME_ENDPOINTS = {
    "Cliente": "client_views.client_home",
    "Entrenador": "role_views.trainer_home",
    "Jefe de sede": "role_views.manager_home",
    "Administrador": "role_views.admin_home",
    "Técnico de mantenimiento": "role_views.technician_home",
}


def _dashboard(role, slug, title, description):
    return render_template(
        "auth/role_dashboard.html",
        role=role,
        role_slug=slug,
        title=title,
        description=description,
    )


@role_views_blueprint.get("/auth/profile")
@require_access(roles=ALL_ROLES)
def account_profile_home():
    identity = current_identity()
    role = identity["user"]["rol"]
    return render_template(
        "auth/account_profile.html",
        role=role,
        dashboard_url=url_for(ROLE_HOME_ENDPOINTS[role]),
    )


@role_views_blueprint.get("/auth/entrenador")
@require_access(roles=("Entrenador",), permission=TRAINER_VIEWS_PERMISSION)
def trainer_home():
    return _dashboard(
        "Entrenador",
        "trainer",
        "Panel de entrenamiento",
        "Rutinas, alumnos autorizados, clases, asistencias y disponibilidad.",
    )


@role_views_blueprint.get("/auth/entrenador/rutinas")
@require_access(roles=("Entrenador",), permission=TRAINER_VIEWS_PERMISSION)
def trainer_routines():
    return render_template("auth/trainer_routines.html")


@role_views_blueprint.get("/auth/entrenador/asistencias")
@require_access(roles=("Entrenador",), permission=TRAINER_VIEWS_PERMISSION)
def trainer_attendance():
    return render_template("auth/trainer_attendance.html")


@role_views_blueprint.get("/auth/jefe-sede")
@require_access(roles=("Jefe de sede",), permission=MANAGER_VIEWS_PERMISSION)
def manager_home():
    return _dashboard(
        "Jefe de sede",
        "manager",
        "Operación de sede",
        "Personal, actividades, horarios y cupos de tu sede asignada.",
    )


@role_views_blueprint.get("/auth/administrador")
@require_access(roles=("Administrador",), permission=ADMIN_VIEWS_PERMISSION)
def admin_home():
    return _dashboard(
        "Administrador",
        "admin",
        "Administración general",
        "Usuarios, sedes, membresías, permisos y reportes operativos.",
    )


@role_views_blueprint.get("/auth/tecnico")
@require_access(
    roles=("Técnico de mantenimiento",), permission=TECHNICIAN_VIEWS_PERMISSION
)
def technician_home():
    return _dashboard(
        "Técnico de mantenimiento",
        "technician",
        "Mantenimiento de sede",
        "Máquinas asignadas, incidencias, estados e historial técnico.",
    )
