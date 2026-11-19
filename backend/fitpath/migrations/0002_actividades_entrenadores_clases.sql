CREATE TABLE entrenadores (
    id_entrenador INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL UNIQUE
        REFERENCES usuarios (id_usuario) ON UPDATE RESTRICT ON DELETE RESTRICT,
    especialidad TEXT NOT NULL
        CHECK (length(trim(especialidad)) > 0 AND especialidad = trim(especialidad))
);

CREATE TABLE entrenador_sede (
    entrenador_id INTEGER NOT NULL
        REFERENCES entrenadores (id_entrenador) ON UPDATE RESTRICT ON DELETE RESTRICT,
    sede_id INTEGER NOT NULL
        REFERENCES sedes (id_sede) ON UPDATE RESTRICT ON DELETE RESTRICT,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    PRIMARY KEY (entrenador_id, sede_id)
);

CREATE TABLE actividades (
    id_actividad INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL COLLATE NOCASE UNIQUE
        CHECK (length(trim(nombre)) > 0 AND nombre = trim(nombre))
);

CREATE TABLE actividad_sede (
    actividad_id INTEGER NOT NULL
        REFERENCES actividades (id_actividad) ON UPDATE RESTRICT ON DELETE RESTRICT,
    sede_id INTEGER NOT NULL
        REFERENCES sedes (id_sede) ON UPDATE RESTRICT ON DELETE RESTRICT,
    habilitada INTEGER NOT NULL DEFAULT 1 CHECK (habilitada IN (0, 1)),
    PRIMARY KEY (actividad_id, sede_id)
);

CREATE TABLE disponibilidad_entrenador (
    id_disponibilidad INTEGER PRIMARY KEY,
    entrenador_id INTEGER NOT NULL,
    sede_id INTEGER NOT NULL,
    dia_semana INTEGER NOT NULL CHECK (dia_semana BETWEEN 1 AND 7),
    hora_inicio TEXT NOT NULL
        CHECK (
            length(hora_inicio) = 5
            AND (
                hora_inicio GLOB '[0-1][0-9]:[0-5][0-9]'
                OR hora_inicio GLOB '2[0-3]:[0-5][0-9]'
            )
        ),
    hora_fin TEXT NOT NULL
        CHECK (
            length(hora_fin) = 5
            AND (
                hora_fin GLOB '[0-1][0-9]:[0-5][0-9]'
                OR hora_fin GLOB '2[0-3]:[0-5][0-9]'
            )
        ),
    UNIQUE (entrenador_id, sede_id, dia_semana, hora_inicio, hora_fin),
    FOREIGN KEY (entrenador_id, sede_id)
        REFERENCES entrenador_sede (entrenador_id, sede_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CHECK (hora_fin > hora_inicio)
);

CREATE TABLE clases (
    id_clase INTEGER PRIMARY KEY,
    actividad_id INTEGER NOT NULL,
    sede_id INTEGER NOT NULL,
    entrenador_id INTEGER NOT NULL,
    inicio_utc TEXT NOT NULL
        CHECK (
            length(inicio_utc) = 20
            AND inicio_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND CAST(substr(inicio_utc, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
            AND CAST(substr(inicio_utc, 12, 2) AS INTEGER) BETWEEN 0 AND 23
            AND strftime('%Y-%m-%dT%H:%M:%SZ', inicio_utc) IS NOT NULL
            AND strftime('%Y-%m-%dT%H:%M:%SZ', inicio_utc) = inicio_utc
        ),
    fin_utc TEXT NOT NULL
        CHECK (
            length(fin_utc) = 20
            AND fin_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND CAST(substr(fin_utc, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
            AND CAST(substr(fin_utc, 12, 2) AS INTEGER) BETWEEN 0 AND 23
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fin_utc) IS NOT NULL
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fin_utc) = fin_utc
        ),
    cupo_maximo INTEGER NOT NULL CHECK (cupo_maximo > 0),
    estado TEXT NOT NULL
        CHECK (estado IN ('programada', 'cancelada', 'realizada')),
    FOREIGN KEY (actividad_id, sede_id)
        REFERENCES actividad_sede (actividad_id, sede_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    FOREIGN KEY (entrenador_id, sede_id)
        REFERENCES entrenador_sede (entrenador_id, sede_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CHECK (fin_utc > inicio_utc)
);


CREATE INDEX idx_entrenador_sede_sede_id
    ON entrenador_sede (sede_id, entrenador_id);
CREATE INDEX idx_actividad_sede_sede_id
    ON actividad_sede (sede_id, actividad_id);
CREATE INDEX idx_disponibilidad_sede_dia
    ON disponibilidad_entrenador (sede_id, dia_semana, entrenador_id);
CREATE INDEX idx_clases_sede_inicio_utc
    ON clases (sede_id, inicio_utc);
CREATE INDEX idx_clases_entrenador_sede_inicio_utc
    ON clases (entrenador_id, sede_id, inicio_utc);
CREATE INDEX idx_clases_actividad_sede_inicio_utc
    ON clases (actividad_id, sede_id, inicio_utc);

CREATE TRIGGER trg_clases_actividad_habilitada_insert
BEFORE INSERT ON clases
WHEN NOT EXISTS (
    SELECT 1
    FROM actividad_sede
    WHERE actividad_id = NEW.actividad_id
      AND sede_id = NEW.sede_id
      AND habilitada = 1
)
BEGIN
    SELECT RAISE(ABORT, 'La actividad no está habilitada en la sede.');
END;

CREATE TRIGGER trg_clases_actividad_habilitada_update
BEFORE UPDATE OF actividad_id, sede_id ON clases
WHEN NOT EXISTS (
    SELECT 1
    FROM actividad_sede
    WHERE actividad_id = NEW.actividad_id
      AND sede_id = NEW.sede_id
      AND habilitada = 1
)
BEGIN
    SELECT RAISE(ABORT, 'La actividad no está habilitada en la sede.');
END;

CREATE TRIGGER trg_clases_entrenador_activo_insert
BEFORE INSERT ON clases
WHEN NOT EXISTS (
    SELECT 1
    FROM entrenador_sede
    WHERE entrenador_id = NEW.entrenador_id
      AND sede_id = NEW.sede_id
      AND activo = 1
)
BEGIN
    SELECT RAISE(ABORT, 'El entrenador no tiene un vínculo activo con la sede.');
END;

CREATE TRIGGER trg_clases_entrenador_activo_update
BEFORE UPDATE OF entrenador_id, sede_id ON clases
WHEN NOT EXISTS (
    SELECT 1
    FROM entrenador_sede
    WHERE entrenador_id = NEW.entrenador_id
      AND sede_id = NEW.sede_id
      AND activo = 1
)
BEGIN
    SELECT RAISE(ABORT, 'El entrenador no tiene un vínculo activo con la sede.');
END;
