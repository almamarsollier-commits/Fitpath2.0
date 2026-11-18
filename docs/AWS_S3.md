# AWS S3 — imágenes privadas de perfil

## Estado de validación

El equipo reportó una prueba real satisfactoria de carga, lectura privada,
reemplazo y eliminación contra el bucket de desarrollo. Esta revisión no
repitió llamadas a AWS; las pruebas automatizadas locales usan dobles y no
comprueban conectividad externa.

El Cliente autenticado puede subir y consultar su propia imagen de perfil mediante:

- `POST /api/v1/client/profile-image`, con `multipart/form-data`, campo `image` y encabezado `X-CSRF-Token`;
- `GET /api/v1/client/profile-image`, que devuelve una URL prefirmada de corta duración.

La clave del objeto se persiste en `clientes.imagen_perfil_clave_s3`. Los objetos usan claves opacas bajo `fitpath/clientes/{id}/perfil`, cifrado S3 `AES256` y ninguna ACL pública. La API exige sesión Cliente, permiso `cliente.datos.ver`, propiedad del perfil y CSRF para la escritura.

Se admiten únicamente JPEG, PNG y WebP de hasta 5 MiB. El backend compara el MIME declarado con la firma real del archivo antes de reutilizar `S3StorageService`.

Las pruebas automatizadas son locales y no acceden a AWS; la validación real
descrita arriba fue reportada por el equipo, no reproducida en esta revisión.

## Configuración

Variables requeridas:

```text
AWS_S3_BUCKET=<bucket privado existente>
AWS_REGION=<región del bucket>
```

Variables opcionales:

```text
AWS_PROFILE=<perfil local, si se usa>
FITPATH_S3_PREFIX=fitpath
FITPATH_S3_ALLOWED_CONTENT_TYPES=image/jpeg,image/png,image/webp
FITPATH_S3_MAX_UPLOAD_BYTES=5242880
FITPATH_S3_DOWNLOAD_TTL_SECONDS=300
```

Boto3 obtiene credenciales mediante su cadena estándar. No guardar `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, tokens, perfiles locales ni `.env` en Git.

## Recuperar los datos del bucket sin compartir secretos

Desde la consola AWS, el nombre se ve en **S3 > Buckets** y la región en la columna **AWS Region** o en **Properties**. Si ya existe un perfil local de AWS CLI, estos comandos no imprimen claves:

```powershell
aws sts get-caller-identity --profile fitpath-dev
aws s3api list-buckets --query "Buckets[].Name" --output table --profile fitpath-dev
aws s3api get-bucket-location --bucket <NOMBRE_BUCKET> --profile fitpath-dev
```

Una ubicación `null` en el último comando corresponde a `us-east-1`.

La clave secreta de acceso no puede recuperarse después de su creación. Para no compartirla por chat, usar preferentemente IAM Identity Center:

```powershell
aws configure sso --profile fitpath-dev
aws sso login --profile fitpath-dev
```

Si la cuenta no usa SSO, crear o rotar una credencial de desarrollo con permisos mínimos y cargarla localmente con `aws configure --profile fitpath-dev`. Los permisos requeridos por este caso son `s3:PutObject`, `s3:GetObject` y `s3:DeleteObject` únicamente sobre `<ARN_BUCKET>/fitpath/clientes/*`. El bloqueo de acceso público del bucket debe permanecer activo.

## Pasos para reproducir la validación real

1. Configurar localmente `AWS_PROFILE`, `AWS_S3_BUCKET` y `AWS_REGION`; no imprimir ni compartir credenciales.
2. Ejecutar migraciones y Flask sin publicar las variables.
3. Iniciar sesión como Cliente y cargar una imagen válida desde **Mi perfil**.
4. Comprobar en S3 que el objeto no es público y que usa cifrado `AES256`.
5. Reiniciar Flask, volver a iniciar sesión y confirmar que dashboard y perfil muestran la imagen mediante otra URL temporal.
6. Probar una credencial sin permisos para verificar que la API responda un error controlado sin perder la referencia anterior.

La integración no debe declararse completa hasta ejecutar esta demostración contra el bucket privado de desarrollo.
