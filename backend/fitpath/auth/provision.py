"""Aprobación local de una vinculación Google, sin endpoint web administrativo."""

import argparse
import getpass
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone

from .. import create_app
from ..database import get_db
from . import GOOGLE_ISSUER
from .identities import utc_timestamp


def approve_link(connection, reference, user_id, now=None):
    """Vincula una identidad pendiente a un usuario existente y activo."""
    digest = hashlib.sha256(reference.encode("utf-8")).hexdigest()
    now = utc_timestamp(now)
    try:
        connection.execute("BEGIN IMMEDIATE")
        request_row = connection.execute(
            """
            SELECT id_solicitud, emisor, subject, vence_utc, estado
            FROM solicitudes_vinculo_google WHERE referencia_sha256 = ?
            """,
            (digest,),
        ).fetchone()
        if (
            request_row is None
            or request_row["estado"] != "pendiente"
            or request_row["vence_utc"] <= now
        ):
            connection.rollback()
            return False

        user = connection.execute(
            "SELECT id_usuario, activo FROM usuarios WHERE id_usuario = ?",
            (user_id,),
        ).fetchone()
        if user is None or user["activo"] != 1:
            connection.rollback()
            return False

        connection.execute(
            """
            INSERT INTO identidades_google (usuario_id, emisor, subject, creado_utc)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, GOOGLE_ISSUER, request_row["subject"], now),
        )
        connection.execute(
            """
            UPDATE solicitudes_vinculo_google
            SET estado = 'aprobada', usuario_id = ?, aprobada_utc = ?
            WHERE id_solicitud = ? AND estado = 'pendiente'
            """,
            (user_id, now, request_row["id_solicitud"]),
        )
        connection.commit()
        return True
    except sqlite3.IntegrityError:
        connection.rollback()
        return False
    except Exception:
        connection.rollback()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("approve", choices=("approve",), help="Aprobar una referencia")
    parser.add_argument("--usuario-id", type=int, required=True)
    args = parser.parse_args(argv)
    reference = getpass.getpass("Referencia de vinculación (no se mostrará): ")
    app = create_app("development")
    with app.app_context():
        approved = approve_link(get_db(), reference, args.usuario_id)
    if approved:
        print("Vinculación aprobada. El usuario puede volver a iniciar sesión con Google.")
        return 0
    print("No se aprobó la referencia: puede haber vencido o el usuario no ser elegible.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
