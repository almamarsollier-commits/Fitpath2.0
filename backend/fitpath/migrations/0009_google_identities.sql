CREATE TABLE identidades_google (
    id_identidad INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL
        REFERENCES usuarios (id_usuario)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    emisor TEXT NOT NULL
        CHECK (emisor = 'https://accounts.google.com'),
    subject TEXT NOT NULL
        CHECK (length(trim(subject)) > 0 AND subject = trim(subject)),
    creado_utc TEXT NOT NULL
        CHECK (length(creado_utc) = 20),
    UNIQUE (emisor, subject),
    UNIQUE (usuario_id)
);

CREATE TABLE solicitudes_vinculo_google (
    id_solicitud INTEGER PRIMARY KEY,
    emisor TEXT NOT NULL
        CHECK (emisor = 'https://accounts.google.com'),
    subject TEXT NOT NULL
        CHECK (length(trim(subject)) > 0 AND subject = trim(subject)),
    referencia_sha256 TEXT NOT NULL UNIQUE
        CHECK (length(referencia_sha256) = 64),
    creado_utc TEXT NOT NULL
        CHECK (length(creado_utc) = 20),
    vence_utc TEXT NOT NULL
        CHECK (length(vence_utc) = 20),
    estado TEXT NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'aprobada', 'rechazada', 'vencida')),
    usuario_id INTEGER
        REFERENCES usuarios (id_usuario)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    aprobada_utc TEXT
        CHECK (aprobada_utc IS NULL OR length(aprobada_utc) = 20),
    CHECK (
        (estado = 'aprobada' AND usuario_id IS NOT NULL AND aprobada_utc IS NOT NULL)
        OR (estado <> 'aprobada' AND usuario_id IS NULL AND aprobada_utc IS NULL)
    ),
    CHECK (vence_utc > creado_utc)
);

CREATE INDEX idx_solicitudes_vinculo_estado_vencimiento
    ON solicitudes_vinculo_google (estado, vence_utc);
