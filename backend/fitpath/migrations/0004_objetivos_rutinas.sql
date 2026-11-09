CREATE TABLE tipos_objetivo (
    id_tipo_objetivo INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE
        CHECK (length(trim(nombre)) > 0 AND nombre = trim(nombre))
);

CREATE TABLE objetivos (
    id_objetivo INTEGER PRIMARY KEY,
    tipo_objetivo_id INTEGER NOT NULL
        REFERENCES tipos_objetivo (id_tipo_objetivo)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    nombre TEXT NOT NULL
        CHECK (length(trim(nombre)) > 0 AND nombre = trim(nombre)),
    descripcion TEXT
        CHECK (
            descripcion IS NULL
            OR (length(trim(descripcion)) > 0 AND descripcion = trim(descripcion))
        ),
    UNIQUE (tipo_objetivo_id, nombre)
);

CREATE TABLE cliente_objetivo (
    cliente_id INTEGER NOT NULL
        REFERENCES clientes (id_cliente)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    objetivo_id INTEGER NOT NULL
        REFERENCES objetivos (id_objetivo)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    PRIMARY KEY (cliente_id, objetivo_id)
);

CREATE TABLE rutinas (
    id_rutina INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL
        CHECK (length(trim(nombre)) > 0 AND nombre = trim(nombre)),
    descripcion TEXT
        CHECK (
            descripcion IS NULL
            OR (length(trim(descripcion)) > 0 AND descripcion = trim(descripcion))
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
    entrenador_id INTEGER NOT NULL
        REFERENCES entrenadores (id_entrenador)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    cliente_id INTEGER NOT NULL
        REFERENCES clientes (id_cliente)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    objetivo_id INTEGER
        REFERENCES objetivos (id_objetivo)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    observaciones_entrenador TEXT
        CHECK (
            observaciones_entrenador IS NULL
            OR (
                length(trim(observaciones_entrenador)) > 0
                AND observaciones_entrenador = trim(observaciones_entrenador)
            )
        )
);

CREATE TABLE ejercicios (
    id_ejercicio INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL
        CHECK (length(trim(nombre)) > 0 AND nombre = trim(nombre)),
    grupo_muscular TEXT
        CHECK (
            grupo_muscular IS NULL
            OR (length(trim(grupo_muscular)) > 0 AND grupo_muscular = trim(grupo_muscular))
        ),
    descripcion TEXT
        CHECK (
            descripcion IS NULL
            OR (length(trim(descripcion)) > 0 AND descripcion = trim(descripcion))
        )
);

CREATE TABLE rutina_ejercicio (
    id_rutina_ejercicio INTEGER PRIMARY KEY,
    rutina_id INTEGER NOT NULL
        REFERENCES rutinas (id_rutina)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    ejercicio_id INTEGER NOT NULL
        REFERENCES ejercicios (id_ejercicio)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    orden INTEGER NOT NULL
        CHECK (typeof(orden) = 'integer' AND orden > 0),
    series INTEGER NOT NULL
        CHECK (typeof(series) = 'integer' AND series > 0),
    repeticiones INTEGER NOT NULL
        CHECK (typeof(repeticiones) = 'integer' AND repeticiones > 0),
    peso_gramos INTEGER
        CHECK (
            peso_gramos IS NULL
            OR (typeof(peso_gramos) = 'integer' AND peso_gramos >= 0)
        ),
    descanso_segundos INTEGER NOT NULL
        CHECK (typeof(descanso_segundos) = 'integer' AND descanso_segundos >= 0),
    UNIQUE (rutina_id, orden)
);

CREATE INDEX idx_cliente_objetivo_objetivo_id
    ON cliente_objetivo (objetivo_id, cliente_id);
CREATE INDEX idx_rutinas_cliente_fecha
    ON rutinas (cliente_id, fecha_creacion_utc DESC);
CREATE INDEX idx_rutinas_entrenador_fecha
    ON rutinas (entrenador_id, fecha_creacion_utc DESC);
CREATE INDEX idx_rutinas_objetivo_id
    ON rutinas (objetivo_id);
CREATE INDEX idx_rutina_ejercicio_ejercicio_id
    ON rutina_ejercicio (ejercicio_id, rutina_id);