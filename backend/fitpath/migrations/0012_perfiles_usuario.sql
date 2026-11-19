CREATE TABLE perfiles_usuario (
    usuario_id INTEGER PRIMARY KEY
        REFERENCES usuarios (id_usuario)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    biografia TEXT
        CHECK (
            biografia IS NULL
            OR (
                length(trim(biografia)) BETWEEN 1 AND 500
                AND biografia = trim(biografia)
            )
        ),
    imagen_perfil_clave_s3 TEXT
        CHECK (
            imagen_perfil_clave_s3 IS NULL
            OR (
                length(imagen_perfil_clave_s3) BETWEEN 1 AND 512
                AND imagen_perfil_clave_s3 = trim(imagen_perfil_clave_s3)
                AND instr(imagen_perfil_clave_s3, char(92)) = 0
                AND instr(imagen_perfil_clave_s3, '..') = 0
            )
        ),
    preferencias_json TEXT NOT NULL DEFAULT '{}'
        CHECK (
            length(preferencias_json) BETWEEN 2 AND 1000
            AND json_valid(preferencias_json)
            AND json_type(preferencias_json) = 'object'
        ),
    actualizado_utc TEXT NOT NULL
        CHECK (
            length(actualizado_utc) = 20
            AND actualizado_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND strftime('%Y-%m-%dT%H:%M:%SZ', actualizado_utc) = actualizado_utc
        )
);
