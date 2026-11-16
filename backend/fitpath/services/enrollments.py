"""Operación interna y transaccional para crear inscripciones."""

import sqlite3
from datetime import datetime, timezone


class EnrollmentError(RuntimeError):
    """Error controlado al crear una inscripción interna."""


class EnrollmentRequestError(EnrollmentError):
    """Los identificadores recibidos no son válidos."""


class EnrollmentConfigurationError(EnrollmentError):
    """La conexión SQLite no satisface las garantías requeridas."""


class ClientNotFoundError(EnrollmentError):
    """No existe el perfil de cliente solicitado."""


class ClassNotFoundError(EnrollmentError):
    """No existe la clase solicitada."""


class ClassUnavailableError(EnrollmentError):
    """La clase no está habilitada para nuevas inscripciones."""


class DuplicateActiveEnrollmentError(EnrollmentError):
    """El cliente ya tiene una inscripción activa en esta clase."""


class ClassFullError(EnrollmentError):
    """La clase no tiene cupos disponibles."""


class ActiveEnrollmentNotFoundError(EnrollmentError):
    """No existe una inscripción activa propia para cancelar."""


class EnrollmentCancellationError(EnrollmentError):
    """La inscripción ya no admite cancelación."""


class EnrollmentStorageError(EnrollmentError):
    """SQLite no pudo completar la operación."""


def _positive_identifier(value, field_name):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EnrollmentRequestError(
            "{} debe ser un entero positivo.".format(field_name)
        )


def _rollback_if_needed(connection):
    if connection.in_transaction:
        connection.rollback()


def create_enrollment(connection, cliente_id, clase_id):
    """Crea una inscripción interna, no una reserva completamente autorizada.

    Comprueba cliente, clase futura programada, actividad habilitada, vínculo
    activo del entrenador, duplicado activo y cupo. No evalúa membresías ni
    autentica ni autoriza al solicitante; no debe exponerse por HTTP o el selector
    demo hasta implementar esos controles.
    """
    _positive_identifier(cliente_id, "cliente_id")
    _positive_identifier(clase_id, "clase_id")

    if connection.in_transaction:
        raise EnrollmentConfigurationError(
            "El servicio requiere una conexión sin transacción previa."
        )

    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
    if foreign_keys is None or foreign_keys[0] != 1:
        raise EnrollmentConfigurationError(
            "El servicio requiere claves foráneas activas."
        )

    try:
        connection.execute("BEGIN IMMEDIATE")

        client = connection.execute(
            "SELECT id_cliente FROM clientes WHERE id_cliente = ?",
            (cliente_id,),
        ).fetchone()
        if client is None:
            raise ClientNotFoundError("No existe el perfil de cliente.")

        scheduled_class = connection.execute(
            """
            SELECT
                clases.estado,
                clases.inicio_utc,
                clases.cupo_maximo,
                actividad_sede.habilitada,
                entrenador_sede.activo
            FROM clases
            LEFT JOIN actividad_sede
                ON actividad_sede.actividad_id = clases.actividad_id
               AND actividad_sede.sede_id = clases.sede_id
            LEFT JOIN entrenador_sede
                ON entrenador_sede.entrenador_id = clases.entrenador_id
               AND entrenador_sede.sede_id = clases.sede_id
            WHERE clases.id_clase = ?
            """,
            (clase_id,),
        ).fetchone()
        if scheduled_class is None:
            raise ClassNotFoundError("No existe la clase solicitada.")

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if (
            scheduled_class[0] != "programada"
            or scheduled_class[1] <= now_utc
            or scheduled_class[3] != 1
            or scheduled_class[4] != 1
        ):
            raise ClassUnavailableError(
                "La clase no está habilitada para nuevas inscripciones."
            )

        duplicate = connection.execute(
            """
            SELECT 1
            FROM inscripciones
            WHERE cliente_id = ? AND clase_id = ? AND estado = ?
            """,
            (cliente_id, clase_id, "activa"),
        ).fetchone()
        if duplicate is not None:
            raise DuplicateActiveEnrollmentError(
                "El cliente ya tiene una inscripción activa en esta clase."
            )

        active_count = connection.execute(
            """
            SELECT count(*)
            FROM inscripciones
            WHERE clase_id = ? AND estado = ?
            """,
            (clase_id, "activa"),
        ).fetchone()[0]
        if active_count >= scheduled_class[2]:
            raise ClassFullError("La clase no tiene cupos disponibles.")

        cursor = connection.execute(
            """
            INSERT INTO inscripciones (cliente_id, clase_id, fecha_utc, estado)
            VALUES (?, ?, ?, ?)
            """,
            (
                cliente_id,
                clase_id,
                now_utc,
                "activa",
            ),
        )
        enrollment_id = cursor.lastrowid
        connection.commit()
        return enrollment_id
    except EnrollmentError:
        _rollback_if_needed(connection)
        raise
    except sqlite3.Error as error:
        _rollback_if_needed(connection)
        raise EnrollmentStorageError(
            "No se pudo completar la inscripción."
        ) from error
    except BaseException:
        _rollback_if_needed(connection)
        raise


def cancel_enrollment(connection, cliente_id, clase_id):
    """Cancela una inscripción propia futura y conserva su historial."""
    _positive_identifier(cliente_id, "cliente_id")
    _positive_identifier(clase_id, "clase_id")
    if connection.in_transaction:
        raise EnrollmentConfigurationError(
            "El servicio requiere una conexión sin transacción previa."
        )
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
    if foreign_keys is None or foreign_keys[0] != 1:
        raise EnrollmentConfigurationError(
            "El servicio requiere claves foráneas activas."
        )
    try:
        connection.execute("BEGIN IMMEDIATE")
        enrollment = connection.execute(
            """
            SELECT i.id_inscripcion, c.inicio_utc, c.estado
            FROM inscripciones AS i
            JOIN clases AS c ON c.id_clase = i.clase_id
            WHERE i.cliente_id = ? AND i.clase_id = ? AND i.estado = 'activa'
            """,
            (cliente_id, clase_id),
        ).fetchone()
        if enrollment is None:
            raise ActiveEnrollmentNotFoundError(
                "No existe una inscripción activa propia para cancelar."
            )
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if enrollment["inicio_utc"] <= now_utc or enrollment["estado"] == "realizada":
            raise EnrollmentCancellationError(
                "La clase ya comenzó y la inscripción no se puede cancelar."
            )
        connection.execute(
            "UPDATE inscripciones SET estado = 'cancelada' WHERE id_inscripcion = ?",
            (enrollment["id_inscripcion"],),
        )
        connection.commit()
        return enrollment["id_inscripcion"]
    except EnrollmentError:
        _rollback_if_needed(connection)
        raise
    except sqlite3.Error as error:
        _rollback_if_needed(connection)
        raise EnrollmentStorageError(
            "No se pudo cancelar la inscripción."
        ) from error
    except BaseException:
        _rollback_if_needed(connection)
        raise
