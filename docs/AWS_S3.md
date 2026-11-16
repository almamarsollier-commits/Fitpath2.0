# AWS S3 — servicio privado

## Estado

El backend dispone de un servicio Flask reutilizable en `backend/fitpath/services/s3_storage.py`. No hay endpoints HTTP porque todavía no están definidos los casos de uso, entidades propietarias ni roles autorizados para cada tipo de archivo.

El servicio:

- exige bucket, región, tamaño máximo y allowlist MIME explícitos;
- mide el contenido real y rechaza archivos vacíos, sobredimensionados o con longitud inconsistente;
- genera claves opacas bajo un prefijo controlado y no conserva el nombre original;
- solicita cifrado S3 `AES256` y nunca establece una ACL pública;
- recupera archivos mediante URLs prefirmadas con duración máxima de 15 minutos;
- traduce errores de AWS a errores internos sin exponer detalles ni credenciales.

## Variables de entorno

```text
AWS_S3_BUCKET=<bucket privado>
AWS_REGION=<región AWS>
FITPATH_S3_PREFIX=fitpath
FITPATH_S3_ALLOWED_CONTENT_TYPES=<lista MIME separada por comas>
FITPATH_S3_MAX_UPLOAD_BYTES=<entero positivo>
FITPATH_S3_DOWNLOAD_TTL_SECONDS=300
```

Boto3 obtiene las credenciales mediante su cadena estándar del entorno. No guardar `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, tokens ni archivos `.env` en Git. El bucket debe mantener bloqueado el acceso público; la aplicación no depende de objetos públicos.

## Pendientes antes de exponer endpoints

1. Aprobar los casos de uso: tipo de archivo, entidad propietaria y motivo de almacenamiento.
2. Definir MIME y tamaño máximo por caso, no como una política genérica inventada.
3. Definir autorización por rol, sede y propiedad del recurso antes de generar una carga o descarga.
4. Decidir persistencia de la clave S3 y política de reemplazo, retención y eliminación.
5. Ejecutar una prueba de integración contra un bucket privado de desarrollo con credenciales válidas y permisos mínimos.

Las pruebas automatizadas actuales usan un cliente falso y no acceden a AWS.
