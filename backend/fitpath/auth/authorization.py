"""Identidad y autorización para rutas privadas de FitPath."""

from functools import wraps

from flask import abort, g, jsonify, redirect, session, url_for

from ..database import get_db


def current_identity():
    """Resuelve el usuario activo y su rol desde SQLite para esta solicitud."""
    if "fitpath_identity" in g:
        return g.fitpath_identity

    user_id = session.get("fitpath_user_id")
    csrf_token = session.get("csrf_token")
    if not user_id or not csrf_token:
        g.fitpath_identity = None
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
        g.fitpath_identity = None
        return None

    g.fitpath_identity = {
        "authenticated": True,
        "csrf_token": csrf_token,
        "user": {
            "id": user["id_usuario"],
            "nombre": user["nombre"],
            "apellido": user["apellido"],
            "rol": user["rol"],
        },
    }
    return g.fitpath_identity


def identity_has_permission(identity, permission):
    """Consulta el permiso desde el rol persistido; nunca confía en el cliente."""
    if identity is None:
        return False
    row = get_db().execute(
        """
        SELECT 1
        FROM usuarios AS u
        JOIN rol_permiso AS rp ON rp.rol_id = u.rol_id
        JOIN permisos AS p ON p.id_permiso = rp.permiso_id
        WHERE u.id_usuario = ? AND u.activo = 1 AND p.clave = ? COLLATE NOCASE
        """,
        (identity["user"]["id"], permission),
    ).fetchone()
    return row is not None


def require_access(*, roles=(), permission=None):
    """Protege una vista mediante sesión, rol y permiso opcional."""
    allowed_roles = frozenset(roles)

    def decorator(view):
        @wraps(view)
        def protected_view(*args, **kwargs):
            identity = current_identity()
            if identity is None:
                return redirect(url_for("auth.login_page"))
            if allowed_roles and identity["user"]["rol"] not in allowed_roles:
                abort(403)
            if permission and not identity_has_permission(identity, permission):
                abort(403)
            return view(*args, **kwargs)

        return protected_view

    return decorator


def require_api_access(*, roles=(), permission=None):
    """Protege una API y responde errores JSON sin redirecciones."""
    allowed_roles = frozenset(roles)

    def decorator(view):
        @wraps(view)
        def protected_view(*args, **kwargs):
            identity = current_identity()
            if identity is None:
                return jsonify({"error": "authentication_required"}), 401
            if allowed_roles and identity["user"]["rol"] not in allowed_roles:
                return jsonify({"error": "permission_denied"}), 403
            if permission and not identity_has_permission(identity, permission):
                return jsonify({"error": "permission_denied"}), 403
            return view(*args, **kwargs)

        return protected_view

    return decorator
