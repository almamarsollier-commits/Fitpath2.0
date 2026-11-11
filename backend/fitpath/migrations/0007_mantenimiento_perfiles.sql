CREATE TABLE tecnicos_mantenimiento (
    id_tecnico INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL UNIQUE
        REFERENCES usuarios (id_usuario)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    sede_id INTEGER NOT NULL
        REFERENCES sedes (id_sede)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE jefes_sede (
    id_jefe_sede INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL UNIQUE
        REFERENCES usuarios (id_usuario)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    sede_id INTEGER NOT NULL
        REFERENCES sedes (id_sede)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE maquinas (
    id_maquina INTEGER PRIMARY KEY,
    sede_id INTEGER NOT NULL
        REFERENCES sedes (id_sede)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    tipo TEXT NOT NULL
        CHECK (length(trim(tipo)) > 0 AND tipo = trim(tipo)),
    estado TEXT NOT NULL
        CHECK (estado IN ('operativa', 'en_reparacion', 'fuera_de_servicio')),
    UNIQUE (id_maquina, sede_id)
);

CREATE TABLE tickets_mantenimiento (
    id_ticket INTEGER PRIMARY KEY,
    maquina_id INTEGER NOT NULL
        REFERENCES maquinas (id_maquina)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    tecnico_id INTEGER NOT NULL
        REFERENCES tecnicos_mantenimiento (id_tecnico)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    fecha_generacion_utc TEXT NOT NULL
        CHECK (
            length(fecha_generacion_utc) = 20
            AND fecha_generacion_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND CAST(substr(fecha_generacion_utc, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
            AND CAST(substr(fecha_generacion_utc, 12, 2) AS INTEGER) BETWEEN 0 AND 23
            AND CAST(substr(fecha_generacion_utc, 15, 2) AS INTEGER) BETWEEN 0 AND 59
            AND CAST(substr(fecha_generacion_utc, 18, 2) AS INTEGER) BETWEEN 0 AND 59
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fecha_generacion_utc, '+0 days') IS NOT NULL
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fecha_generacion_utc, '+0 days') = fecha_generacion_utc
        ),
    descripcion TEXT NOT NULL
        CHECK (length(trim(descripcion)) > 0 AND descripcion = trim(descripcion)),
    estado TEXT NOT NULL
        CHECK (estado IN ('abierto', 'en_proceso', 'resuelto', 'cancelado')),
    UNIQUE (id_ticket, maquina_id)
);

CREATE TABLE historial_mantenimiento (
    id_historial INTEGER PRIMARY KEY,
    maquina_id INTEGER NOT NULL
        REFERENCES maquinas (id_maquina)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    ticket_id INTEGER,
    tecnico_id INTEGER NOT NULL
        REFERENCES tecnicos_mantenimiento (id_tecnico)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    fecha_utc TEXT NOT NULL
        CHECK (
            length(fecha_utc) = 20
            AND fecha_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND CAST(substr(fecha_utc, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
            AND CAST(substr(fecha_utc, 12, 2) AS INTEGER) BETWEEN 0 AND 23
            AND CAST(substr(fecha_utc, 15, 2) AS INTEGER) BETWEEN 0 AND 59
            AND CAST(substr(fecha_utc, 18, 2) AS INTEGER) BETWEEN 0 AND 59
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fecha_utc, '+0 days') IS NOT NULL
            AND strftime('%Y-%m-%dT%H:%M:%SZ', fecha_utc, '+0 days') = fecha_utc
        ),
    estado_anterior TEXT
        CHECK (
            estado_anterior IS NULL
            OR estado_anterior IN ('operativa', 'en_reparacion', 'fuera_de_servicio')
        ),
    estado_nuevo TEXT NOT NULL
        CHECK (estado_nuevo IN ('operativa', 'en_reparacion', 'fuera_de_servicio')),
    descripcion TEXT
        CHECK (
            descripcion IS NULL
            OR (length(trim(descripcion)) > 0 AND descripcion = trim(descripcion))
        ),
    FOREIGN KEY (ticket_id, maquina_id)
        REFERENCES tickets_mantenimiento (id_ticket, maquina_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE INDEX idx_tecnicos_mantenimiento_sede
    ON tecnicos_mantenimiento (sede_id, id_tecnico);
CREATE INDEX idx_jefes_sede_sede
    ON jefes_sede (sede_id, id_jefe_sede);
CREATE INDEX idx_maquinas_sede_estado
    ON maquinas (sede_id, estado, id_maquina);
CREATE INDEX idx_tickets_maquina_fecha
    ON tickets_mantenimiento (maquina_id, fecha_generacion_utc DESC);
CREATE INDEX idx_tickets_tecnico_fecha
    ON tickets_mantenimiento (tecnico_id, fecha_generacion_utc DESC);
CREATE INDEX idx_historial_maquina_fecha
    ON historial_mantenimiento (maquina_id, fecha_utc DESC);
CREATE INDEX idx_historial_ticket_maquina
    ON historial_mantenimiento (ticket_id, maquina_id);
CREATE INDEX idx_historial_tecnico_fecha
    ON historial_mantenimiento (tecnico_id, fecha_utc DESC);

CREATE TRIGGER trg_tickets_same_site_insert
BEFORE INSERT ON tickets_mantenimiento
WHEN NOT EXISTS (
    SELECT 1
    FROM maquinas AS maquina
    JOIN tecnicos_mantenimiento AS tecnico
      ON tecnico.id_tecnico = NEW.tecnico_id
    WHERE maquina.id_maquina = NEW.maquina_id
      AND maquina.sede_id = tecnico.sede_id
)
BEGIN
    SELECT RAISE(ABORT, 'El técnico y la máquina deben pertenecer a la misma sede.');
END;

CREATE TRIGGER trg_tickets_same_site_update
BEFORE UPDATE OF maquina_id, tecnico_id ON tickets_mantenimiento
WHEN NOT EXISTS (
    SELECT 1
    FROM maquinas AS maquina
    JOIN tecnicos_mantenimiento AS tecnico
      ON tecnico.id_tecnico = NEW.tecnico_id
    WHERE maquina.id_maquina = NEW.maquina_id
      AND maquina.sede_id = tecnico.sede_id
)
BEGIN
    SELECT RAISE(ABORT, 'El técnico y la máquina deben pertenecer a la misma sede.');
END;

CREATE TRIGGER trg_historial_same_site_insert
BEFORE INSERT ON historial_mantenimiento
WHEN NOT EXISTS (
    SELECT 1
    FROM maquinas AS maquina
    JOIN tecnicos_mantenimiento AS tecnico
      ON tecnico.id_tecnico = NEW.tecnico_id
    WHERE maquina.id_maquina = NEW.maquina_id
      AND maquina.sede_id = tecnico.sede_id
)
BEGIN
    SELECT RAISE(ABORT, 'El técnico y la máquina del historial deben pertenecer a la misma sede.');
END;

CREATE TRIGGER trg_historial_same_site_update
BEFORE UPDATE OF maquina_id, tecnico_id ON historial_mantenimiento
WHEN NOT EXISTS (
    SELECT 1
    FROM maquinas AS maquina
    JOIN tecnicos_mantenimiento AS tecnico
      ON tecnico.id_tecnico = NEW.tecnico_id
    WHERE maquina.id_maquina = NEW.maquina_id
      AND maquina.sede_id = tecnico.sede_id
)
BEGIN
    SELECT RAISE(ABORT, 'El técnico y la máquina del historial deben pertenecer a la misma sede.');
END;

CREATE TRIGGER trg_tecnico_site_preserves_history
BEFORE UPDATE OF sede_id ON tecnicos_mantenimiento
WHEN EXISTS (
    SELECT 1
    FROM tickets_mantenimiento AS ticket
    JOIN maquinas AS maquina ON maquina.id_maquina = ticket.maquina_id
    WHERE ticket.tecnico_id = OLD.id_tecnico
      AND maquina.sede_id <> NEW.sede_id
)
OR EXISTS (
    SELECT 1
    FROM historial_mantenimiento AS historial
    JOIN maquinas AS maquina ON maquina.id_maquina = historial.maquina_id
    WHERE historial.tecnico_id = OLD.id_tecnico
      AND maquina.sede_id <> NEW.sede_id
)
BEGIN
    SELECT RAISE(ABORT, 'No se puede cambiar de sede un técnico con historial incompatible.');
END;

CREATE TRIGGER trg_maquina_site_preserves_history
BEFORE UPDATE OF sede_id ON maquinas
WHEN EXISTS (
    SELECT 1
    FROM tickets_mantenimiento AS ticket
    JOIN tecnicos_mantenimiento AS tecnico ON tecnico.id_tecnico = ticket.tecnico_id
    WHERE ticket.maquina_id = OLD.id_maquina
      AND tecnico.sede_id <> NEW.sede_id
)
OR EXISTS (
    SELECT 1
    FROM historial_mantenimiento AS historial
    JOIN tecnicos_mantenimiento AS tecnico ON tecnico.id_tecnico = historial.tecnico_id
    WHERE historial.maquina_id = OLD.id_maquina
      AND tecnico.sede_id <> NEW.sede_id
)
BEGIN
    SELECT RAISE(ABORT, 'No se puede cambiar de sede una máquina con historial incompatible.');
END;
