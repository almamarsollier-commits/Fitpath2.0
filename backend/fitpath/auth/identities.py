"""Persistencia de identidades Google y solicitudes locales de vinculación."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from . import GOOGLE_ISSUER


LINK_REFERENCE_LIFETIME = timedelta(minutes=15)


def utc_timestamp(value=None):
    value = value or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def find_active_user(connection, issuer, subject):
    return connection.execute(
        """
        SELECT u.id_usuario, u.nombre, u.apellido, u.rol_id, r.nombre AS rol
        FROM identidades_google AS i
        JOIN usuarios AS u ON u.id_usuario = i.usuario_id
        JOIN roles AS r ON r.id_rol = u.rol_id
        WHERE i.emisor = ? AND i.subject = ? AND u.activo = 1
        """,
        (issuer, subject),
    ).fetchone()


def create_link_request(connection, issuer, subject):
    """Guarda solo el hash; el código aleatorio se muestra una única vez."""
    if issuer != GOOGLE_ISSUER or not isinstance(subject, str) or not subject.strip():
        raise ValueError("Identidad Google inválida.")

    reference = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + LINK_REFERENCE_LIFETIME
    connection.execute(
        """
        INSERT INTO solicitudes_vinculo_google (
            emisor, subject, referencia_sha256, creado_utc, vence_utc
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            issuer,
            subject,
            hashlib.sha256(reference.encode("utf-8")).hexdigest(),
            utc_timestamp(now),
            utc_timestamp(expires),
        ),
    )
    connection.commit()
    return reference, utc_timestamp(expires)
