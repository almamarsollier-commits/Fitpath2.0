CREATE TABLE progresos (
    id_progreso INTEGER PRIMARY KEY,
    cliente_id INTEGER NOT NULL
        REFERENCES clientes (id_cliente)
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
    peso_kg REAL
        CHECK (
            peso_kg IS NULL
            OR (
                typeof(peso_kg) IN ('integer', 'real')
                AND peso_kg > 0
            )
        ),
    porcentaje_grasa REAL
        CHECK (
            porcentaje_grasa IS NULL
            OR (
                typeof(porcentaje_grasa) IN ('integer', 'real')
                AND porcentaje_grasa BETWEEN 0 AND 100
            )
        ),
    rendimiento_ejercicios TEXT
        CHECK (
            rendimiento_ejercicios IS NULL
            OR (
                length(trim(rendimiento_ejercicios)) > 0
                AND rendimiento_ejercicios = trim(rendimiento_ejercicios)
            )
        ),
    observaciones TEXT
        CHECK (
            observaciones IS NULL
            OR (length(trim(observaciones)) > 0 AND observaciones = trim(observaciones))
        )
);

CREATE TABLE planes_alimentacion (
    id_plan_alimentacion INTEGER PRIMARY KEY,
    cliente_id INTEGER NOT NULL
        REFERENCES clientes (id_cliente)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    objetivo_id INTEGER NOT NULL
        REFERENCES objetivos (id_objetivo)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    nombre TEXT NOT NULL
        CHECK (length(trim(nombre)) > 0 AND nombre = trim(nombre)),
    descripcion TEXT
        CHECK (
            descripcion IS NULL
            OR (length(trim(descripcion)) > 0 AND descripcion = trim(descripcion))
        ),
    indicaciones TEXT
        CHECK (
            indicaciones IS NULL
            OR (length(trim(indicaciones)) > 0 AND indicaciones = trim(indicaciones))
        ),
    fecha_creacion_utc TEXT NOT NULL
        CHECK (
            length(fecha_creacion_utc) = 20
            AND fecha_creacion_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND CAST(substr(fecha_creacion_utc, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
            AND CAST(substr(fecha_creacion_utc, 12, 2) AS INTEGER) BETWEEN 0 AND 23
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fecha_creacion_utc) IS NOT NULL
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fecha_creacion_utc) = fecha_creacion_utc
        ),
    fecha_actualizacion_utc TEXT NOT NULL
        CHECK (
            length(fecha_actualizacion_utc) = 20
            AND fecha_actualizacion_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND CAST(substr(fecha_actualizacion_utc, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
            AND CAST(substr(fecha_actualizacion_utc, 12, 2) AS INTEGER) BETWEEN 0 AND 23
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fecha_actualizacion_utc) IS NOT NULL
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fecha_actualizacion_utc) = fecha_actualizacion_utc
        ),
    CHECK (fecha_actualizacion_utc >= fecha_creacion_utc)
);

CREATE INDEX idx_progresos_cliente_fecha
    ON progresos (cliente_id, fecha_utc DESC);
CREATE INDEX idx_planes_alimentacion_cliente_fecha
    ON planes_alimentacion (cliente_id, fecha_creacion_utc DESC);
CREATE INDEX idx_planes_alimentacion_objetivo_id
    ON planes_alimentacion (objetivo_id);