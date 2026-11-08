CREATE TABLE roles (
    id_rol INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL COLLATE NOCASE UNIQUE
        CHECK (length(trim(nombre)) > 0)
);

CREATE TABLE permisos (
    id_permiso INTEGER PRIMARY KEY,
    clave TEXT NOT NULL COLLATE NOCASE UNIQUE
        CHECK (length(trim(clave)) > 0),
    descripcion TEXT
        CHECK (descripcion IS NULL OR (length(trim(descripcion)) > 0 AND descripcion = trim(descripcion)))
);

CREATE TABLE rol_permiso (
    rol_id INTEGER NOT NULL
        REFERENCES roles (id_rol) ON UPDATE RESTRICT ON DELETE RESTRICT,
    permiso_id INTEGER NOT NULL
        REFERENCES permisos (id_permiso) ON UPDATE RESTRICT ON DELETE RESTRICT,
    PRIMARY KEY (rol_id, permiso_id)
);

CREATE TABLE usuarios (
    id_usuario INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL
        CHECK (length(trim(nombre)) > 0 AND nombre = trim(nombre)),
    apellido TEXT NOT NULL
        CHECK (length(trim(apellido)) > 0 AND apellido = trim(apellido)),
    nombre_usuario TEXT NOT NULL COLLATE NOCASE UNIQUE
        CHECK (
            length(trim(nombre_usuario)) > 0
            AND nombre_usuario = trim(nombre_usuario)
            AND nombre_usuario COLLATE BINARY = lower(nombre_usuario)
        ),
    email TEXT NOT NULL COLLATE NOCASE UNIQUE
        CHECK (
            length(trim(email)) > 0
            AND email = trim(email)
            AND email COLLATE BINARY = lower(email)
        ),
    telefono TEXT
        CHECK (
            telefono IS NULL
            OR (length(trim(telefono)) > 0 AND telefono = trim(telefono))
        ),
    rol_id INTEGER NOT NULL
        REFERENCES roles (id_rol) ON UPDATE RESTRICT ON DELETE RESTRICT,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE sedes (
    id_sede INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL
        CHECK (length(trim(nombre)) > 0 AND nombre = trim(nombre)),
    direccion TEXT NOT NULL
        CHECK (length(trim(direccion)) > 0 AND direccion = trim(direccion)),
    zona_horaria TEXT NOT NULL
        CHECK (length(trim(zona_horaria)) > 0 AND zona_horaria = trim(zona_horaria))
);

CREATE INDEX idx_usuarios_rol_id ON usuarios (rol_id);
CREATE INDEX idx_rol_permiso_permiso_id ON rol_permiso (permiso_id, rol_id);
