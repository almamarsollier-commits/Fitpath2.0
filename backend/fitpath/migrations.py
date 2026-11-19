"""Migrador SQL versionado con una transacción atómica por archivo."""

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


MIGRATION_FILENAME = re.compile(r"^(?P<version>[0-9]{4})_(?P<name>[a-z][a-z0-9_]*)\.sql$")
TRANSACTION_CONTROL = re.compile(
    r"^(BEGIN|COMMIT|END|ROLLBACK|SAVEPOINT|RELEASE)\b", re.IGNORECASE
)


class MigrationError(RuntimeError):
    """Una migración no es válida o no pudo aplicarse de forma atómica."""


def _sql_after_leading_comments(sql):
    """Quita espacios y comentarios iniciales para validar un statement."""
    remaining = sql
    while True:
        remaining = remaining.lstrip()
        if remaining.startswith("--"):
            newline = remaining.find("\n")
            if newline == -1:
                return ""
            remaining = remaining[newline + 1 :]
            continue
        if remaining.startswith("/*"):
            end = remaining.find("*/", 2)
            if end == -1:
                return ""
            remaining = remaining[end + 2 :]
            continue
        return remaining


def _statements(script):
    """Divide SQL respetando strings y cuerpos de triggers mediante SQLite."""
    buffer = []
    for character in script:
        buffer.append(character)
        if character == ";":
            candidate = "".join(buffer)
            if sqlite3.complete_statement(candidate):
                statement = candidate.strip()
                meaningful = _sql_after_leading_comments(statement).strip().strip(";").strip()
                if meaningful:
                    yield statement
                buffer = []

    remainder = "".join(buffer)
    if _sql_after_leading_comments(remainder).strip():
        raise MigrationError("La migración termina con una sentencia SQL incompleta.")


def _migration_files(directory):
    path = Path(directory)
    try:
        if not path.exists():
            return []
        if not path.is_dir():
            raise MigrationError("La ubicación de migraciones no es una carpeta.")
        files = [
            file
            for file in path.iterdir()
            if file.is_file() and file.suffix.lower() == ".sql"
        ]
    except OSError as error:
        raise MigrationError("No se pudo leer la carpeta de migraciones.") from error
    migrations = []
    seen_versions = set()

    for file in files:
        match = MIGRATION_FILENAME.fullmatch(file.name)
        if match is None:
            raise MigrationError(
                "Nombre de migración inválido: {!r}.".format(file.name)
            )
        version = int(match.group("version"))
        if version < 1 or version in seen_versions:
            raise MigrationError("La versión de migración está repetida o no es válida.")
        seen_versions.add(version)
        migrations.append((version, file.name, file))

    migrations.sort(key=lambda item: item[0])
    expected = list(range(1, len(migrations) + 1))
    if [item[0] for item in migrations] != expected:
        raise MigrationError("Las versiones SQL deben ser consecutivas desde 0001.")
    return migrations


def _ensure_registry(connection):
    if connection.in_transaction:
        raise MigrationError("El migrador requiere una conexión sin transacción abierta.")

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY CHECK (version > 0),
                name TEXT NOT NULL UNIQUE,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(schema_migrations)")
        }
        if not {"version", "name", "checksum", "applied_at"}.issubset(columns):
            raise MigrationError("El registro schema_migrations tiene una estructura incompatible.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _foreign_key_violations(connection):
    return connection.execute("PRAGMA foreign_key_check").fetchall()


def _apply_one(connection, version, name, script, checksum):
    if connection.in_transaction:
        raise MigrationError("El migrador requiere una conexión sin transacción abierta.")

    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _statements(script):
            if TRANSACTION_CONTROL.match(_sql_after_leading_comments(statement)):
                raise MigrationError(
                    "El archivo no debe administrar sus propias transacciones."
                )
            connection.execute(statement)

        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise MigrationError("La migración desactivó las claves foráneas.")
        violations = _foreign_key_violations(connection)
        if violations:
            raise MigrationError("La migración dejó referencias foráneas inválidas.")

        applied_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, checksum, applied_at)
            VALUES (?, ?, ?, ?)
            """,
            (version, name, checksum, applied_at),
        )
        connection.commit()
    except Exception as error:
        connection.rollback()
        if isinstance(error, MigrationError):
            raise MigrationError("Falló {}: {}".format(name, error)) from error
        if isinstance(error, sqlite3.Error):
            raise MigrationError(
                "Falló {} por un error SQL: {}".format(name, error)
            ) from error
        raise


def apply_migrations(connection, migrations_dir):
    """Aplica nuevas migraciones en orden y devuelve sus versiones aplicadas."""
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
    if foreign_keys is None or foreign_keys[0] != 1:
        raise MigrationError("La conexión debe tener PRAGMA foreign_keys = 1.")

    _ensure_registry(connection)
    migrations = _migration_files(migrations_dir)
    by_version = {version: (name, file) for version, name, file in migrations}
    applied = {
        row["version"]: row
        for row in connection.execute(
            "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
        )
    }

    missing_files = sorted(set(applied) - set(by_version))
    if missing_files:
        raise MigrationError(
            "Faltan archivos para versiones ya aplicadas: {}.".format(missing_files)
        )
    if sorted(applied) != list(range(1, len(applied) + 1)):
        raise MigrationError("El registro de versiones aplicadas contiene saltos.")

    newly_applied = []
    for version, name, file in migrations:
        try:
            script = file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise MigrationError(
                "No se pudo leer la migración {}.".format(name)
            ) from error
        checksum = hashlib.sha256(script.encode("utf-8")).hexdigest()

        if version in applied:
            recorded = applied[version]
            if recorded["name"] != name or recorded["checksum"] != checksum:
                raise MigrationError(
                    "La migración aplicada {} fue modificada; cree una versión nueva.".format(
                        name
                    )
                )
            continue

        _apply_one(connection, version, name, script, checksum)
        newly_applied.append(version)

    if _foreign_key_violations(connection):
        raise MigrationError("La base contiene referencias foráneas inválidas.")

    return tuple(newly_applied)
