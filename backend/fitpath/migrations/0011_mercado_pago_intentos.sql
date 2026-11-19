ALTER TABLE deudas
ADD COLUMN estado TEXT NOT NULL DEFAULT 'pendiente'
    CHECK (estado IN ('pendiente', 'pagada', 'anulada'));

ALTER TABLE deudas
ADD COLUMN pagada_utc TEXT
    CHECK (
        pagada_utc IS NULL
        OR (
            length(pagada_utc) = 20
            AND pagada_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND strftime('%Y-%m-%dT%H:%M:%SZ', pagada_utc, '+0 days') = pagada_utc
        )
    );

CREATE TRIGGER validar_estado_deuda_insert
BEFORE INSERT ON deudas
FOR EACH ROW
WHEN NOT (
    (NEW.estado = 'pagada' AND NEW.pagada_utc IS NOT NULL)
    OR (NEW.estado <> 'pagada' AND NEW.pagada_utc IS NULL)
)
BEGIN
    SELECT RAISE(ABORT, 'estado y fecha de pago de deuda inconsistentes');
END;

CREATE TRIGGER validar_estado_deuda_update
BEFORE UPDATE OF estado, pagada_utc ON deudas
FOR EACH ROW
WHEN NOT (
    (NEW.estado = 'pagada' AND NEW.pagada_utc IS NOT NULL)
    OR (NEW.estado <> 'pagada' AND NEW.pagada_utc IS NULL)
)
BEGIN
    SELECT RAISE(ABORT, 'estado y fecha de pago de deuda inconsistentes');
END;

CREATE TABLE intentos_pago (
    id_intento INTEGER PRIMARY KEY,
    deuda_id INTEGER NOT NULL
        REFERENCES deudas (id_deuda)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    pago_id INTEGER NOT NULL UNIQUE
        REFERENCES pagos (id_pago)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    proveedor TEXT NOT NULL DEFAULT 'mercado_pago'
        CHECK (proveedor = 'mercado_pago'),
    referencia_externa TEXT NOT NULL UNIQUE
        CHECK (
            length(referencia_externa) BETWEEN 16 AND 80
            AND referencia_externa = trim(referencia_externa)
        ),
    preferencia_proveedor_id TEXT UNIQUE
        CHECK (
            preferencia_proveedor_id IS NULL
            OR (
                length(preferencia_proveedor_id) BETWEEN 1 AND 128
                AND preferencia_proveedor_id = trim(preferencia_proveedor_id)
            )
        ),
    pago_proveedor_id TEXT UNIQUE
        CHECK (
            pago_proveedor_id IS NULL
            OR (
                length(pago_proveedor_id) BETWEEN 1 AND 128
                AND pago_proveedor_id = trim(pago_proveedor_id)
            )
        ),
    checkout_url TEXT
        CHECK (
            checkout_url IS NULL
            OR (
                length(checkout_url) BETWEEN 9 AND 2048
                AND checkout_url GLOB 'https://*'
            )
        ),
    importe_unidades_menores INTEGER NOT NULL
        CHECK (
            typeof(importe_unidades_menores) = 'integer'
            AND importe_unidades_menores > 0
        ),
    moneda TEXT NOT NULL
        REFERENCES monedas (codigo)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    concepto TEXT NOT NULL
        CHECK (length(trim(concepto)) > 0 AND concepto = trim(concepto)),
    estado TEXT NOT NULL
        CHECK (
            estado IN (
                'creado', 'pendiente', 'aprobado', 'rechazado',
                'cancelado', 'error'
            )
        ),
    estado_detalle TEXT
        CHECK (
            estado_detalle IS NULL
            OR (
                length(estado_detalle) BETWEEN 1 AND 255
                AND estado_detalle = trim(estado_detalle)
            )
        ),
    creado_utc TEXT NOT NULL
        CHECK (
            length(creado_utc) = 20
            AND strftime('%Y-%m-%dT%H:%M:%SZ', creado_utc, '+0 days') = creado_utc
        ),
    actualizado_utc TEXT NOT NULL
        CHECK (
            length(actualizado_utc) = 20
            AND strftime('%Y-%m-%dT%H:%M:%SZ', actualizado_utc, '+0 days') = actualizado_utc
            AND actualizado_utc >= creado_utc
        )
);

CREATE UNIQUE INDEX uq_intentos_pago_activo_por_deuda
    ON intentos_pago (deuda_id)
    WHERE estado IN ('creado', 'pendiente');
CREATE INDEX idx_intentos_pago_deuda_fecha
    ON intentos_pago (deuda_id, creado_utc DESC, id_intento DESC);
CREATE INDEX idx_intentos_pago_estado_fecha
    ON intentos_pago (estado, actualizado_utc DESC);

CREATE TRIGGER validar_pago_intento_insert
BEFORE INSERT ON intentos_pago
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM pagos
    WHERE id_pago = NEW.pago_id AND deuda_id = NEW.deuda_id
)
BEGIN
    SELECT RAISE(ABORT, 'el pago del intento no pertenece a la deuda');
END;

CREATE TRIGGER validar_pago_intento_update
BEFORE UPDATE OF deuda_id, pago_id ON intentos_pago
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM pagos
    WHERE id_pago = NEW.pago_id AND deuda_id = NEW.deuda_id
)
BEGIN
    SELECT RAISE(ABORT, 'el pago del intento no pertenece a la deuda');
END;

CREATE TABLE eventos_webhook_pago (
    id_evento INTEGER PRIMARY KEY,
    proveedor TEXT NOT NULL DEFAULT 'mercado_pago'
        CHECK (proveedor = 'mercado_pago'),
    request_id TEXT NOT NULL UNIQUE
        CHECK (length(trim(request_id)) BETWEEN 1 AND 128),
    recurso_tipo TEXT NOT NULL
        CHECK (recurso_tipo = 'payment'),
    recurso_id TEXT NOT NULL
        CHECK (length(trim(recurso_id)) BETWEEN 1 AND 128),
    resultado TEXT NOT NULL
        CHECK (resultado IN ('procesado', 'ignorado')),
    recibido_utc TEXT NOT NULL
        CHECK (
            length(recibido_utc) = 20
            AND strftime('%Y-%m-%dT%H:%M:%SZ', recibido_utc, '+0 days') = recibido_utc
        )
);

CREATE INDEX idx_eventos_webhook_recurso
    ON eventos_webhook_pago (recurso_tipo, recurso_id, recibido_utc DESC);
