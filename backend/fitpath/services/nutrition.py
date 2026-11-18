"""Consultas reutilizables y sin mutaciones para planes de alimentación."""


def _serialize_plan(row):
    return {
        "id": row["id"],
        "cliente_id": row["cliente_id"],
        "nombre": row["nombre"],
        "descripcion": row["descripcion"],
        "indicaciones": row["indicaciones"],
        "fecha_creacion_utc": row["fecha_creacion_utc"],
        "fecha_actualizacion_utc": row["fecha_actualizacion_utc"],
        "objetivo": {
            "id": row["objetivo_id"],
            "nombre": row["objetivo"],
            "tipo": row["tipo_objetivo"],
        },
    }


def list_nutrition_plans(connection, client_id):
    """Devuelve todos los planes del cliente, sin alterar su historial."""
    rows = connection.execute(
        """
        SELECT p.id_plan_alimentacion AS id, p.cliente_id, p.nombre,
               p.descripcion, p.indicaciones, p.fecha_creacion_utc,
               p.fecha_actualizacion_utc, o.id_objetivo AS objetivo_id,
               o.nombre AS objetivo, t.nombre AS tipo_objetivo
        FROM planes_alimentacion AS p
        JOIN objetivos AS o ON o.id_objetivo = p.objetivo_id
        JOIN tipos_objetivo AS t ON t.id_tipo_objetivo = o.tipo_objetivo_id
        WHERE p.cliente_id = ?
        ORDER BY p.fecha_creacion_utc DESC, p.id_plan_alimentacion DESC
        """,
        (client_id,),
    ).fetchall()
    return [_serialize_plan(row) for row in rows]


def get_nutrition_plan(connection, client_id, plan_id):
    """Busca un plan dentro del ámbito del cliente indicado."""
    row = connection.execute(
        """
        SELECT p.id_plan_alimentacion AS id, p.cliente_id, p.nombre,
               p.descripcion, p.indicaciones, p.fecha_creacion_utc,
               p.fecha_actualizacion_utc, o.id_objetivo AS objetivo_id,
               o.nombre AS objetivo, t.nombre AS tipo_objetivo
        FROM planes_alimentacion AS p
        JOIN objetivos AS o ON o.id_objetivo = p.objetivo_id
        JOIN tipos_objetivo AS t ON t.id_tipo_objetivo = o.tipo_objetivo_id
        WHERE p.id_plan_alimentacion = ? AND p.cliente_id = ?
        """,
        (plan_id, client_id),
    ).fetchone()
    return _serialize_plan(row) if row is not None else None
