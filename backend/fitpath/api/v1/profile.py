"""Imagen de perfil privada del usuario autenticado."""

import hmac
import io
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from ...auth.authorization import (
    current_identity,
    identity_has_permission,
    require_api_access,
)
from ...database import get_db
from ...permissions import (
    ADMIN_DATA_PERMISSION,
    CLIENT_DATA_PERMISSION,
    MANAGER_DATA_PERMISSION,
    TECHNICIAN_DATA_PERMISSION,
    TRAINER_DATA_PERMISSION,
)
from ...services.s3_storage import (
    StorageConfigurationError,
    StorageOperationError,
    StorageValidationError,
    get_s3_storage,
)


profile_api_blueprint = Blueprint("profile_api", __name__)
PROFILE_PERMISSION_BY_ROLE = {
    "Cliente": CLIENT_DATA_PERMISSION,
    "Entrenador": TRAINER_DATA_PERMISSION,
    "Jefe de sede": MANAGER_DATA_PERMISSION,
    "Administrador": ADMIN_DATA_PERMISSION,
    "Técnico de mantenimiento": TECHNICIAN_DATA_PERMISSION,
}
client_profile_required = require_api_access(
    roles=("Cliente",), permission=CLIENT_DATA_PERMISSION
)


def profile_access_required(view):
    @wraps(view)
    def protected_view(*args, **kwargs):
        identity = current_identity()
        if identity is None:
            return jsonify({"error": "authentication_required"}), 401
        permission = PROFILE_PERMISSION_BY_ROLE.get(identity["user"]["rol"])
        if permission is None or not identity_has_permission(identity, permission):
            return jsonify({"error": "permission_denied"}), 403
        return view(*args, **kwargs)

    return protected_view


@profile_api_blueprint.after_request
def disable_private_cache(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _user_profile():
    identity = current_identity()
    return get_db().execute(
        """
        SELECT u.id_usuario,
               c.id_cliente,
               p.imagen_perfil_clave_s3,
               c.imagen_perfil_clave_s3 AS imagen_cliente_legacy
        FROM usuarios u
        LEFT JOIN clientes c ON c.usuario_id = u.id_usuario
        LEFT JOIN perfiles_usuario p ON p.usuario_id = u.id_usuario
        WHERE u.id_usuario = ?
        """,
        (identity["user"]["id"],),
    ).fetchone()


def _csrf_is_valid():
    identity = current_identity()
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = identity["csrf_token"] if identity else ""
    return bool(supplied and expected and hmac.compare_digest(supplied, expected))


def _detect_image_content_type(content):
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if (
        len(content) >= 12
        and content.startswith(b"RIFF")
        and content[8:12] == b"WEBP"
    ):
        return "image/webp"
    raise StorageValidationError("El contenido no es una imagen JPEG, PNG o WebP válida.")


def _owned_namespace(profile):
    if profile["id_cliente"] is not None:
        return f"clientes/{profile['id_cliente']}/perfil"
    return f"usuarios/{profile['id_usuario']}/perfil"


def _allowed_prefixes(storage, profile):
    prefixes = {
        f"{storage.settings.prefix}/usuarios/{profile['id_usuario']}/perfil/"
    }
    if profile["id_cliente"] is not None:
        prefixes.add(
            f"{storage.settings.prefix}/clientes/{profile['id_cliente']}/perfil/"
        )
    return prefixes


def _key_belongs_to_user(storage, profile, object_key):
    return isinstance(object_key, str) and any(
        object_key.startswith(prefix) for prefix in _allowed_prefixes(storage, profile)
    )


def _stored_key(profile):
    return profile["imagen_perfil_clave_s3"] or profile["imagen_cliente_legacy"]


def _image_payload(storage, profile, object_key):
    if not object_key:
        return {"image": None}
    if not _key_belongs_to_user(storage, profile, object_key):
        current_app.logger.error("Referencia S3 de perfil fuera del espacio del usuario.")
        return None
    return {
        "image": {
            "url": storage.create_download_url(object_key),
            "expires_in": storage.settings.download_ttl_seconds,
        }
    }


@profile_api_blueprint.get("/api/v1/me/profile-image")
@profile_access_required
def get_profile_image():
    profile = _user_profile()
    if profile is None:
        return jsonify({"error": "user_not_found"}), 404
    try:
        storage = get_s3_storage()
        payload = _image_payload(storage, profile, _stored_key(profile))
        if payload is None:
            return jsonify({"error": "profile_image_reference_invalid"}), 500
        return jsonify(payload)
    except StorageConfigurationError:
        return jsonify({"error": "storage_not_configured"}), 503
    except (StorageValidationError, StorageOperationError):
        return jsonify({"error": "profile_image_unavailable"}), 503


@profile_api_blueprint.get("/api/v1/client/profile-image")
@client_profile_required
def get_client_profile_image():
    return get_profile_image()


@profile_api_blueprint.post("/api/v1/me/profile-image")
@profile_access_required
def upload_profile_image():
    if not _csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400

    profile = _user_profile()
    if profile is None:
        return jsonify({"error": "user_not_found"}), 404
    uploaded = request.files.get("image")
    if uploaded is None:
        return jsonify({"error": "image_required"}), 400

    try:
        storage = get_s3_storage()
        maximum = storage.settings.max_upload_bytes
        content = uploaded.stream.read(maximum + 1)
        if not content:
            raise StorageValidationError("La imagen está vacía.")
        if len(content) > maximum:
            raise StorageValidationError("La imagen supera el tamaño permitido.")

        detected_type = _detect_image_content_type(content)
        declared_type = str(uploaded.mimetype or "").strip().lower()
        if declared_type != detected_type:
            raise StorageValidationError("El tipo declarado no coincide con el contenido.")

        object_key = storage.upload_private(
            io.BytesIO(content),
            namespace=_owned_namespace(profile),
            content_type=detected_type,
            content_length=len(content),
        )
    except StorageConfigurationError:
        return jsonify({"error": "storage_not_configured"}), 503
    except StorageValidationError as error:
        return jsonify({"error": "invalid_profile_image", "message": str(error)}), 400
    except StorageOperationError:
        return jsonify({"error": "profile_image_upload_failed"}), 503

    connection = get_db()
    previous_key = _stored_key(profile)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO perfiles_usuario
                (usuario_id, imagen_perfil_clave_s3, actualizado_utc)
            VALUES (?, ?, ?)
            ON CONFLICT(usuario_id) DO UPDATE SET
                imagen_perfil_clave_s3 = excluded.imagen_perfil_clave_s3,
                actualizado_utc = excluded.actualizado_utc
            """,
            (profile["id_usuario"], object_key, _utc_now()),
        )
        if profile["id_cliente"] is not None:
            connection.execute(
                "UPDATE clientes SET imagen_perfil_clave_s3 = ? WHERE id_cliente = ?",
                (object_key, profile["id_cliente"]),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        try:
            storage.delete_private(object_key)
        except StorageOperationError:
            current_app.logger.warning("No se pudo limpiar una carga S3 no persistida.")
        current_app.logger.exception("No se pudo persistir la imagen de perfil.")
        return jsonify({"error": "profile_image_persistence_failed"}), 500

    if (
        previous_key
        and previous_key != object_key
        and _key_belongs_to_user(storage, profile, previous_key)
    ):
        try:
            storage.delete_private(previous_key)
        except (StorageValidationError, StorageOperationError):
            current_app.logger.warning("No se pudo retirar la imagen de perfil anterior.")
    elif previous_key and previous_key != object_key:
        current_app.logger.warning(
            "No se retiró una imagen anterior fuera del espacio del usuario."
        )

    try:
        payload = _image_payload(storage, profile, object_key)
        return jsonify(payload), 201
    except StorageOperationError:
        return jsonify({"image": None, "uploaded": True}), 201


@profile_api_blueprint.post("/api/v1/client/profile-image")
@client_profile_required
def upload_client_profile_image():
    return upload_profile_image()
