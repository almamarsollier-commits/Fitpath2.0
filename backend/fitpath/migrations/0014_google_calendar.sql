CREATE TABLE autorizaciones_google_calendar (
    usuario_id INTEGER PRIMARY KEY
        REFERENCES usuarios (id_usuario)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    refresh_token_cifrado TEXT NOT NULL
        CHECK (length(refresh_token_cifrado) >= 80),
    alcance TEXT NOT NULL
        CHECK (
            instr(
                alcance,
                'https://www.googleapis.com/auth/calendar.events.owned'
            ) > 0
        ),
    creado_utc TEXT NOT NULL CHECK (length(creado_utc) = 20),
    actualizado_utc TEXT NOT NULL CHECK (length(actualizado_utc) = 20)
);

CREATE TABLE eventos_google_calendar (
    id_evento_calendar INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL
        REFERENCES usuarios (id_usuario)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    inscripcion_id INTEGER NOT NULL UNIQUE
        REFERENCES inscripciones (id_inscripcion)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    google_calendar_id TEXT NOT NULL DEFAULT 'primary'
        CHECK (google_calendar_id = 'primary'),
    google_event_id TEXT NOT NULL
        CHECK (length(google_event_id) BETWEEN 5 AND 1024),
    google_event_url TEXT
        CHECK (
            google_event_url IS NULL
            OR google_event_url GLOB 'https://*'
        ),
    creado_utc TEXT NOT NULL CHECK (length(creado_utc) = 20),
    UNIQUE (usuario_id, google_event_id)
);

CREATE INDEX idx_eventos_calendar_usuario
    ON eventos_google_calendar (usuario_id, creado_utc DESC);
