"""Imagen de perfil privada del Cliente autenticado."""

import hmac
import io

from flask import Blueprint, current_app, jsonify, request

from ...auth.authorization import current_identity, require_api_access
from ...database import get_db
from ...permissions import CLIENT_DATA_PERMISSION
from ...services.s3_storage import (
    StorageConfigurationError,
    StorageOperationError,
    StorageValidationError,
    get_s3_storage,
)


profile_api_blueprint = Blueprint(
    "profile_api", __name__, url_prefix="/api/v1/client/profile-image"
)
client_profile_required = require_api_access(
    roles=("Cliente",), permission=CLIENT_DATA_PERMISSION
)


@profile_api_blueprint.after_request
def disable_private_cache(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _client_profile():
    identity = current_identity()
    return get_db().execute(
        """
        SELECT id_cliente, imagen_perfil_clave_s3
        FROM clientes
        WHERE usuario_id = ?
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


def _owned_namespace(storage, client_id):
    return f"clientes/{client_id}/perfil"


def _key_belongs_to_client(storage, client_id, object_key):
    prefix = f"{storage.settings.prefix}/{_owned_namespace(storage, client_id)}/"
    return isinstance(object_key, str) and object_key.startswith(prefix)


def _image_payload(storage, client_id, object_key):
    if not object_key:
        return {"image": None}
    if not _key_belongs_to_client(storage, client_id, object_key):
        current_app.logger.error("Referencia S3 de perfil fuera del espacio del Cliente.")
        return None
    return {
        "image": {
            "url": storage.create_download_url(object_key),
            "expires_in": storage.settings.download_ttl_seconds,
        }
    }


@profile_api_blueprint.get("")
@client_profile_required
def get_profile_image():
    profile = _client_profile()
    if profile is None:
        return jsonify({"error": "client_profile_required"}), 403
    try:
        storage = get_s3_storage()
        payload = _image_payload(
            storage, profile["id_cliente"], profile["imagen_perfil_clave_s3"]
        )
        if payload is None:
            return jsonify({"error": "profile_image_reference_invalid"}), 500
        return jsonify(payload)
    except StorageConfigurationError:
        return jsonify({"error": "storage_not_configured"}), 503
    except (StorageValidationError, StorageOperationError):
        return jsonify({"error": "profile_image_unavailable"}), 503


@profile_api_blueprint.post("")
@client_profile_required
def upload_profile_image():
    if not _csrf_is_valid():
        return jsonify({"error": "csrf_failed"}), 400

    profile = _client_profile()
    if profile is None:
        return jsonify({"error": "client_profile_required"}), 403
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
            namespace=_owned_namespace(storage, profile["id_cliente"]),
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
    previous_key = profile["imagen_perfil_clave_s3"]
    try:
        connection.execute("BEGIN IMMEDIATE")
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
        and _key_belongs_to_client(storage, profile["id_cliente"], previous_key)
    ):
        try:
            storage.delete_private(previous_key)
        except (StorageValidationError, StorageOperationError):
            current_app.logger.warning("No se pudo retirar la imagen de perfil anterior.")
    elif previous_key and previous_key != object_key:
        current_app.logger.warning("No se retiró una imagen anterior fuera del espacio del Cliente.")

    try:
        payload = _image_payload(storage, profile["id_cliente"], object_key)
        return jsonify(payload), 201
    except StorageOperationError:
        return jsonify({"image": None, "uploaded": True}), 201
