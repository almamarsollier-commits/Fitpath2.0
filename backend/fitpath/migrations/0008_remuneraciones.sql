CREATE TABLE remuneraciones (
    id_remuneracion INTEGER PRIMARY KEY,
    clase_id INTEGER NOT NULL UNIQUE
        REFERENCES clases (id_clase)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    importe_unidades_menores INTEGER NOT NULL
        CHECK (
            typeof(importe_unidades_menores) = 'integer'
            AND importe_unidades_menores >= 0
        ),
    moneda TEXT NOT NULL
        REFERENCES monedas (codigo)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    estado_liquidacion TEXT NOT NULL
        CHECK (estado_liquidacion IN ('pendiente', 'liquidada', 'anulada')),
    liquidada_utc TEXT
        CHECK (
            liquidada_utc IS NULL
            OR (
                length(liquidada_utc) = 20
                AND liquidada_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
                AND CAST(substr(liquidada_utc, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
                AND CAST(substr(liquidada_utc, 12, 2) AS INTEGER) BETWEEN 0 AND 23
                AND CAST(substr(liquidada_utc, 15, 2) AS INTEGER) BETWEEN 0 AND 59
                AND CAST(substr(liquidada_utc, 18, 2) AS INTEGER) BETWEEN 0 AND 59
                AND strftime('%Y-%m-%dT%H:%M:%SZ', liquidada_utc, '+0 days') IS NOT NULL
                AND strftime('%Y-%m-%dT%H:%M:%SZ', liquidada_utc, '+0 days') = liquidada_utc
            )
        ),
    CHECK (
        (estado_liquidacion = 'liquidada' AND liquidada_utc IS NOT NULL)
        OR (estado_liquidacion <> 'liquidada' AND liquidada_utc IS NULL)
    )
);

CREATE INDEX idx_remuneraciones_estado_clase
    ON remuneraciones (estado_liquidacion, clase_id);
CREATE INDEX idx_remuneraciones_moneda
    ON remuneraciones (moneda);

CREATE TRIGGER trg_clase_trainer_immutable_after_remuneration
BEFORE UPDATE OF entrenador_id ON clases
WHEN NEW.entrenador_id <> OLD.entrenador_id
 AND EXISTS (
    SELECT 1
    FROM remuneraciones
    WHERE clase_id = OLD.id_clase
)
BEGIN
    SELECT RAISE(
        ABORT,
        'No se puede reasignar el entrenador de una clase con remuneración registrada.'
    );
END;

CREATE TRIGGER trg_remuneracion_clase_immutable
BEFORE UPDATE OF clase_id ON remuneraciones
WHEN NEW.clase_id <> OLD.clase_id
BEGIN
    SELECT RAISE(ABORT, 'No se puede cambiar la clase de una remuneración histórica.');
END;

CREATE TRIGGER trg_remuneracion_preserve_history
BEFORE DELETE ON remuneraciones
BEGIN
    SELECT RAISE(ABORT, 'Las remuneraciones se anulan; no se eliminan del historial.');
END;
