ALTER TABLE clientes
ADD COLUMN imagen_perfil_clave_s3 TEXT
    CHECK (
        imagen_perfil_clave_s3 IS NULL
        OR (
            length(imagen_perfil_clave_s3) BETWEEN 1 AND 512
            AND imagen_perfil_clave_s3 = trim(imagen_perfil_clave_s3)
            AND instr(imagen_perfil_clave_s3, char(92)) = 0
            AND instr(imagen_perfil_clave_s3, '..') = 0
        )
    );
