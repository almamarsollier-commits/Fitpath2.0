"""Validaciones de zona horaria, disponibilidad y agenda de entrenadores."""

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class ScheduleValidationError(Exception):
    """La clase no cumple una regla segura de programación."""

    code = "schedule_validation_failed"


class SiteTimezoneError(ScheduleValidationError):
    code = "site_timezone_invalid"


class TrainerUnavailableError(ScheduleValidationError):
    code = "trainer_unavailable"


class TrainerScheduleConflictError(ScheduleValidationError):
    code = "trainer_schedule_conflict"


def validate_timezone_name(value, field="zona_horaria"):
    """Comprueba que el valor pueda resolverse como identificador IANA."""

    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as error:
        raise ValueError(field) from error
    return value


def parse_utc_datetime(value):
    """Convierte el formato UTC canónico usado por SQLite."""

    return datetime.strptime(value, UTC_FORMAT).replace(tzinfo=timezone.utc)


def trainer_is_available(
    connection,
    *,
    trainer_id,
    site_id,
    start_utc,
    end_utc,
    exclude_availability_id=None,
):
    """Indica si una franja UTC queda contenida en la disponibilidad local."""

    site = connection.execute(
        """
        SELECT s.zona_horaria
        FROM sedes AS s
        JOIN entrenador_sede AS es ON es.sede_id = s.id_sede
        WHERE s.id_sede = ? AND es.entrenador_id = ? AND es.activo = 1
        """,
        (site_id, trainer_id),
    ).fetchone()
    if site is None:
        return False
    try:
        site_timezone = ZoneInfo(site["zona_horaria"])
    except (ZoneInfoNotFoundError, ValueError, TypeError) as error:
        raise SiteTimezoneError from error

    local_start = parse_utc_datetime(start_utc).astimezone(site_timezone)
    local_end = parse_utc_datetime(end_utc).astimezone(site_timezone)
    query = """
        SELECT hora_inicio, hora_fin
        FROM disponibilidad_entrenador
        WHERE entrenador_id = ? AND sede_id = ? AND dia_semana = ?
    """
    parameters = [trainer_id, site_id, local_start.isoweekday()]
    if exclude_availability_id is not None:
        query += " AND id_disponibilidad <> ?"
        parameters.append(exclude_availability_id)
    availability = connection.execute(query, parameters).fetchall()
    start_time = local_start.time()
    end_time = local_end.time()
    return (
        local_start.date() == local_end.date()
        and end_time >= start_time
        and any(
            time.fromisoformat(row["hora_inicio"])
            <= start_time
            <= end_time
            <= time.fromisoformat(row["hora_fin"])
            for row in availability
        )
    )


def validate_trainer_schedule(
    connection,
    *,
    trainer_id,
    site_id,
    start_utc,
    end_utc,
    exclude_class_id=None,
):
    """Valida disponibilidad local y ausencia de solapamientos no cancelados."""

    if not trainer_is_available(
        connection,
        trainer_id=trainer_id,
        site_id=site_id,
        start_utc=start_utc,
        end_utc=end_utc,
    ):
        raise TrainerUnavailableError

    query = """
        SELECT 1 FROM clases
        WHERE entrenador_id = ? AND estado <> 'cancelada'
          AND inicio_utc < ? AND fin_utc > ?
    """
    parameters = [trainer_id, end_utc, start_utc]
    if exclude_class_id is not None:
        query += " AND id_clase <> ?"
        parameters.append(exclude_class_id)
    if connection.execute(query, parameters).fetchone() is not None:
        raise TrainerScheduleConflictError
