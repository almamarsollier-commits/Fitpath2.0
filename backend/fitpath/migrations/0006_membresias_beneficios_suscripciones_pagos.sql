CREATE TABLE monedas (
    codigo TEXT PRIMARY KEY NOT NULL
        CHECK (
            length(codigo) = 3
            AND codigo GLOB '[A-Z][A-Z][A-Z]'
            AND codigo = upper(codigo)
        ),
    decimales INTEGER NOT NULL
        CHECK (typeof(decimales) = 'integer' AND decimales BETWEEN 0 AND 4)
);

CREATE TABLE membresias (
    id_membresia INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE
        CHECK (length(trim(nombre)) > 0 AND nombre = trim(nombre)),
    precio_unidades_menores INTEGER NOT NULL
        CHECK (
            typeof(precio_unidades_menores) = 'integer'
            AND precio_unidades_menores >= 0
        ),
    moneda TEXT NOT NULL
        REFERENCES monedas (codigo)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    descripcion TEXT
        CHECK (
            descripcion IS NULL
            OR (length(trim(descripcion)) > 0 AND descripcion = trim(descripcion))
        ),
    activa INTEGER NOT NULL
        CHECK (typeof(activa) = 'integer' AND activa IN (0, 1))
);

CREATE TABLE beneficios (
    id_beneficio INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE
        CHECK (length(trim(nombre)) > 0 AND nombre = trim(nombre)),
    descripcion TEXT
        CHECK (
            descripcion IS NULL
            OR (length(trim(descripcion)) > 0 AND descripcion = trim(descripcion))
        )
);

CREATE TABLE membresia_beneficio (
    membresia_id INTEGER NOT NULL
        REFERENCES membresias (id_membresia)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    beneficio_id INTEGER NOT NULL
        REFERENCES beneficios (id_beneficio)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    PRIMARY KEY (membresia_id, beneficio_id)
);

CREATE TABLE cliente_membresia (
    id_cliente_membresia INTEGER PRIMARY KEY,
    cliente_id INTEGER NOT NULL
        REFERENCES clientes (id_cliente)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    membresia_id INTEGER NOT NULL
        REFERENCES membresias (id_membresia)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    fecha_inicio TEXT NOT NULL
        CHECK (
            length(fecha_inicio) = 10
            AND fecha_inicio GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            AND date(fecha_inicio, '+0 days') IS NOT NULL
            AND date(fecha_inicio, '+0 days') = fecha_inicio
        ),
    fecha_fin TEXT
        CHECK (
            fecha_fin IS NULL
            OR (
                length(fecha_fin) = 10
                AND fecha_fin GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                AND date(fecha_fin, '+0 days') IS NOT NULL
                AND date(fecha_fin, '+0 days') = fecha_fin
            )
        ),
    estado TEXT NOT NULL
        CHECK (estado IN ('activa', 'vencida', 'cancelada')),
    UNIQUE (id_cliente_membresia, cliente_id),
    CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
);

CREATE TABLE deudas (
    id_deuda INTEGER PRIMARY KEY,
    cliente_id INTEGER NOT NULL
        REFERENCES clientes (id_cliente)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    cliente_membresia_id INTEGER,
    concepto TEXT NOT NULL
        CHECK (length(trim(concepto)) > 0 AND concepto = trim(concepto)),
    importe_unidades_menores INTEGER NOT NULL
        CHECK (
            typeof(importe_unidades_menores) = 'integer'
            AND importe_unidades_menores > 0
        ),
    moneda TEXT NOT NULL
        REFERENCES monedas (codigo)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    vence_el TEXT NOT NULL
        CHECK (
            length(vence_el) = 10
            AND vence_el GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            AND date(vence_el, '+0 days') IS NOT NULL
            AND date(vence_el, '+0 days') = vence_el
        ),
    FOREIGN KEY (cliente_membresia_id, cliente_id)
        REFERENCES cliente_membresia (id_cliente_membresia, cliente_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE pagos (
    id_pago INTEGER PRIMARY KEY,
    deuda_id INTEGER NOT NULL
        REFERENCES deudas (id_deuda)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    importe_unidades_menores INTEGER NOT NULL
        CHECK (
            typeof(importe_unidades_menores) = 'integer'
            AND importe_unidades_menores > 0
        ),
    metodo TEXT NOT NULL
        CHECK (metodo IN ('efectivo', 'transferencia', 'digital')),
    estado TEXT NOT NULL
        CHECK (estado IN ('en_proceso', 'realizado', 'anulado')),
    creado_utc TEXT NOT NULL
        CHECK (
            length(creado_utc) = 20
            AND creado_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND CAST(substr(creado_utc, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
            AND CAST(substr(creado_utc, 12, 2) AS INTEGER) BETWEEN 0 AND 23
            AND CAST(substr(creado_utc, 15, 2) AS INTEGER) BETWEEN 0 AND 59
            AND CAST(substr(creado_utc, 18, 2) AS INTEGER) BETWEEN 0 AND 59
            AND strftime('%Y-%m-%dT%H:%M:%SZ', creado_utc, '+0 days') IS NOT NULL
            AND strftime('%Y-%m-%dT%H:%M:%SZ', creado_utc, '+0 days') = creado_utc
        ),
    realizado_utc TEXT
        CHECK (
            realizado_utc IS NULL
            OR (
                length(realizado_utc) = 20
                AND realizado_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
                AND CAST(substr(realizado_utc, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
                AND CAST(substr(realizado_utc, 12, 2) AS INTEGER) BETWEEN 0 AND 23
                AND CAST(substr(realizado_utc, 15, 2) AS INTEGER) BETWEEN 0 AND 59
                AND CAST(substr(realizado_utc, 18, 2) AS INTEGER) BETWEEN 0 AND 59
                AND strftime('%Y-%m-%dT%H:%M:%SZ', realizado_utc, '+0 days') IS NOT NULL
                AND strftime('%Y-%m-%dT%H:%M:%SZ', realizado_utc, '+0 days') = realizado_utc
            )
        ),
    CHECK (
        (estado = 'realizado' AND realizado_utc IS NOT NULL)
        OR (estado <> 'realizado' AND realizado_utc IS NULL)
    )
);

CREATE INDEX idx_membresias_moneda ON membresias (moneda);
CREATE INDEX idx_membresias_activa_nombre ON membresias (activa, nombre);
CREATE INDEX idx_membresia_beneficio_beneficio
    ON membresia_beneficio (beneficio_id, membresia_id);
CREATE UNIQUE INDEX uq_cliente_membresia_activa
    ON cliente_membresia (cliente_id)
    WHERE estado = 'activa';
CREATE INDEX idx_cliente_membresia_cliente_fecha
    ON cliente_membresia (cliente_id, fecha_inicio DESC);
CREATE INDEX idx_cliente_membresia_membresia
    ON cliente_membresia (membresia_id, id_cliente_membresia);
CREATE INDEX idx_deudas_cliente_vencimiento
    ON deudas (cliente_id, vence_el, id_deuda);
CREATE INDEX idx_deudas_cliente_membresia
    ON deudas (cliente_membresia_id, cliente_id)
    WHERE cliente_membresia_id IS NOT NULL;
CREATE INDEX idx_deudas_moneda ON deudas (moneda);
CREATE INDEX idx_pagos_deuda_estado_creado
    ON pagos (deuda_id, estado, creado_utc DESC);
