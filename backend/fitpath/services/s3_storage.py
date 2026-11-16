"""Almacenamiento privado S3, sin endpoints ni credenciales en el código."""

import re
import secrets
import tempfile
from dataclasses import dataclass

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import current_app, g


SAFE_PATH = re.compile(r"^[a-z0-9][a-z0-9/_-]{0,127}$")


class StorageConfigurationError(RuntimeError):
    """La política S3 necesaria no está configurada de forma segura."""


class StorageValidationError(ValueError):
    """El archivo o la clave no cumple la política configurada."""


class StorageOperationError(RuntimeError):
    """S3 rechazó una operación sin exponer detalles internos."""


def _positive_integer(value, label, *, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise StorageConfigurationError(f"{label} debe ser un entero positivo.") from error
    if parsed <= 0 or (maximum is not None and parsed > maximum):
        raise StorageConfigurationError(f"{label} está fuera del rango permitido.")
    return parsed


@dataclass(frozen=True)
class S3StorageSettings:
    bucket: str
    region: str
    prefix: str
    allowed_content_types: frozenset
    max_upload_bytes: int
    download_ttl_seconds: int

    @classmethod
    def from_mapping(cls, config):
        bucket = str(config.get("S3_BUCKET") or "").strip()
        region = str(config.get("S3_REGION") or "").strip()
        prefix = str(config.get("S3_PREFIX") or "").strip().strip("/")
        raw_types = config.get("S3_ALLOWED_CONTENT_TYPES")
        if isinstance(raw_types, str):
            allowed_types = frozenset(
                value.strip().lower() for value in raw_types.split(",") if value.strip()
            )
        else:
            allowed_types = frozenset(
                str(value).strip().lower() for value in (raw_types or ()) if str(value).strip()
            )

        if not bucket or not region:
            raise StorageConfigurationError("S3 requiere bucket y región explícitos.")
        if not SAFE_PATH.fullmatch(prefix):
            raise StorageConfigurationError("El prefijo S3 no es válido.")
        if not allowed_types:
            raise StorageConfigurationError("S3 requiere una allowlist MIME explícita.")
        if any("/" not in content_type for content_type in allowed_types):
            raise StorageConfigurationError("La allowlist MIME contiene un valor inválido.")

        return cls(
            bucket=bucket,
            region=region,
            prefix=prefix,
            allowed_content_types=allowed_types,
            max_upload_bytes=_positive_integer(
                config.get("S3_MAX_UPLOAD_BYTES"), "S3_MAX_UPLOAD_BYTES"
            ),
            download_ttl_seconds=_positive_integer(
                config.get("S3_DOWNLOAD_TTL_SECONDS"),
                "S3_DOWNLOAD_TTL_SECONDS",
                maximum=900,
            ),
        )


class S3StorageService:
    def __init__(self, client, settings):
        self.client = client
        self.settings = settings

    def _new_object_key(self, namespace):
        normalized = str(namespace or "").strip().strip("/")
        if not SAFE_PATH.fullmatch(normalized) or ".." in normalized.split("/"):
            raise StorageValidationError("El espacio de almacenamiento no es válido.")
        return f"{self.settings.prefix}/{normalized}/{secrets.token_hex(16)}"

    def _validated_key(self, object_key):
        value = str(object_key or "").strip()
        expected_prefix = f"{self.settings.prefix}/"
        if (
            not value.startswith(expected_prefix)
            or "\\" in value
            or ".." in value.split("/")
            or len(value) > 512
        ):
            raise StorageValidationError("La clave del objeto no es válida.")
        return value

    def _buffer_upload(self, file_object, declared_length=None):
        if declared_length is not None and (
            isinstance(declared_length, bool)
            or not isinstance(declared_length, int)
            or declared_length <= 0
            or declared_length > self.settings.max_upload_bytes
        ):
            raise StorageValidationError("El tamaño declarado no está permitido.")

        buffered = tempfile.SpooledTemporaryFile(
            max_size=min(self.settings.max_upload_bytes, 1024 * 1024), mode="w+b"
        )
        total = 0
        try:
            while True:
                chunk = file_object.read(64 * 1024)
                if not chunk:
                    break
                if not isinstance(chunk, bytes):
                    raise StorageValidationError("El archivo debe entregarse como bytes.")
                total += len(chunk)
                if total > self.settings.max_upload_bytes:
                    raise StorageValidationError("El archivo supera el tamaño permitido.")
                buffered.write(chunk)
            if total == 0:
                raise StorageValidationError("El archivo está vacío.")
            if declared_length is not None and total != declared_length:
                raise StorageValidationError("El tamaño real no coincide con el declarado.")
            buffered.seek(0)
            return buffered
        except Exception:
            buffered.close()
            raise

    def upload_private(self, file_object, *, namespace, content_type, content_length=None):
        normalized_type = str(content_type or "").strip().lower()
        if normalized_type not in self.settings.allowed_content_types:
            raise StorageValidationError("El tipo de archivo no está permitido.")

        object_key = self._new_object_key(namespace)
        buffered = self._buffer_upload(file_object, content_length)
        try:
            self.client.upload_fileobj(
                buffered,
                self.settings.bucket,
                object_key,
                ExtraArgs={
                    "ContentType": normalized_type,
                    "ServerSideEncryption": "AES256",
                },
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageOperationError("No se pudo almacenar el archivo.") from error
        finally:
            buffered.close()
        return object_key

    def create_download_url(self, object_key):
        key = self._validated_key(object_key)
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.settings.bucket, "Key": key},
                ExpiresIn=self.settings.download_ttl_seconds,
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageOperationError("No se pudo preparar la descarga.") from error

    def delete_private(self, object_key):
        """Elimina una clave privada validada; nunca acepta rutas ajenas al prefijo."""
        key = self._validated_key(object_key)
        try:
            self.client.delete_object(Bucket=self.settings.bucket, Key=key)
        except (BotoCoreError, ClientError) as error:
            raise StorageOperationError("No se pudo eliminar el archivo.") from error


def create_s3_storage(config, client=None):
    settings = S3StorageSettings.from_mapping(config)
    if client is None:
        client = boto3.client("s3", region_name=settings.region)
    return S3StorageService(client, settings)


def get_s3_storage():
    """Devuelve un servicio por contexto Flask, creado solo cuando se solicita."""
    if "fitpath_s3_storage" not in g:
        g.fitpath_s3_storage = create_s3_storage(current_app.config)
    return g.fitpath_s3_storage
