ALTER TABLE rutinas
ADD COLUMN activa INTEGER NOT NULL DEFAULT 1 CHECK (activa IN (0, 1));

CREATE INDEX idx_rutinas_cliente_activa_fecha
    ON rutinas (cliente_id, activa, fecha_creacion_utc DESC);

CREATE TRIGGER trg_rutinas_preservar_historial
BEFORE DELETE ON rutinas
BEGIN
    SELECT RAISE(ABORT, 'Las rutinas se desactivan; no se eliminan del historial.');
END;
