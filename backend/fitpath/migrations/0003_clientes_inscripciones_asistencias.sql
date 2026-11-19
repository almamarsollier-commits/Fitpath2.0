CREATE TABLE clientes (
    id_cliente INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL UNIQUE
        REFERENCES usuarios (id_usuario) ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE inscripciones (
    id_inscripcion INTEGER PRIMARY KEY,
    cliente_id INTEGER NOT NULL
        REFERENCES clientes (id_cliente) ON UPDATE RESTRICT ON DELETE RESTRICT,
    clase_id INTEGER NOT NULL
        REFERENCES clases (id_clase) ON UPDATE RESTRICT ON DELETE RESTRICT,
    fecha_utc TEXT NOT NULL
        CHECK (
            length(fecha_utc) = 20
            AND fecha_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND CAST(substr(fecha_utc, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
            AND CAST(substr(fecha_utc, 12, 2) AS INTEGER) BETWEEN 0 AND 23
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fecha_utc) IS NOT NULL
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fecha_utc) = fecha_utc
        ),
    estado TEXT NOT NULL
        CHECK (estado IN ('activa', 'cancelada'))
);

CREATE UNIQUE INDEX uq_inscripciones_activas_cliente_clase
    ON inscripciones (cliente_id, clase_id)
    WHERE estado = 'activa';
CREATE INDEX idx_inscripciones_cliente_fecha
    ON inscripciones (cliente_id, fecha_utc DESC);
CREATE INDEX idx_inscripciones_clase_estado
    ON inscripciones (clase_id, estado);

CREATE TABLE asistencias (
    id_asistencia INTEGER PRIMARY KEY,
    inscripcion_id INTEGER NOT NULL UNIQUE
        REFERENCES inscripciones (id_inscripcion)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    fecha_utc TEXT NOT NULL
        CHECK (
            length(fecha_utc) = 20
            AND fecha_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND CAST(substr(fecha_utc, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
            AND CAST(substr(fecha_utc, 12, 2) AS INTEGER) BETWEEN 0 AND 23
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fecha_utc) IS NOT NULL
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fecha_utc) = fecha_utc
        ),
    estado TEXT NOT NULL
        CHECK (estado IN ('presente', 'ausente'))
);