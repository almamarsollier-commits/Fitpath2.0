# Google Auth — M11

## Configuración local sin guardar secretos

El backend lee estas variables de entorno:

- `SECRET_KEY`: clave aleatoria de Flask, distinta por entorno.
- `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`: credenciales del cliente OAuth web.
- `GOOGLE_REDIRECT_URI`: valor opcional; por defecto `http://localhost:5000/auth/google/callback`.

En Google Cloud Console creá un cliente OAuth de tipo **Aplicación web** y agregá exactamente esta URI en **URIs de redirección autorizados**:

```text
http://localhost:5000/auth/google/callback
```

No hace falta agregar un origen JavaScript para este flujo de servidor. Google permite HTTP en `localhost`; cualquier entorno publicado debe usar HTTPS y su URI exacta. No copies credenciales a este repositorio.

En PowerShell, desde `C:\Proyectos\Fitpath2.0`:

```powershell
$env:SECRET_KEY = "$(& .\.venv\Scripts\python.exe -c 'import secrets; print(secrets.token_urlsafe(48))')"
$env:GOOGLE_CLIENT_ID = "<ID del cliente web>"
$env:GOOGLE_CLIENT_SECRET = "<secreto del cliente web>"
$env:GOOGLE_REDIRECT_URI = "http://localhost:5000/auth/google/callback"
..\.venv\Scripts\python.exe -m backend.migrate --environment development
..\.venv\Scripts\python.exe -m flask --app backend.fitpath:create_app run --host localhost --port 5000
```

Abrí `http://localhost:5000/auth/login` en Chrome. El login, callback, sesión y logout usan el mismo origen Flask; no uses Live Server para esta pantalla.

## Rutas

- `GET /auth/login`: pantalla de acceso.
- `GET /auth/google/login`: inicio OIDC con state y nonce.
- `GET /auth/google/callback`: callback Authorization Code.
- `GET /auth/me`: identidad mínima de FitPath; el rol y el estado se consultan en SQLite.
- `POST /auth/logout`: logout con token CSRF.

`GET /auth/me` entrega el token CSRF de la sesión autenticada para que el cliente del mismo origen pueda enviar el formulario de logout. No devuelve tokens OAuth.

La base de M11 no crea usuarios automáticamente. Para preparar el único usuario ficticio Cliente de demostración (con perfil en `clientes`, rol 1 y correo reservado `.invalid`), ejecutá:

```powershell
..\.venv\Scripts\python.exe -m backend.fitpath.auth.demo
```

El comando es idempotente e informa el ID FitPath. No crea identidad Google ni permisos.

Si la identidad Google verificada aún no está vinculada, se muestra una referencia aleatoria que vence en 15 minutos. El administrador la aprueba localmente, fuera de HTTP:

```powershell
..\.venv\Scripts\python.exe -m backend.fitpath.auth approve --usuario-id 123
```

El comando solicita la referencia sin imprimirla. La tabla guarda únicamente su hash. El usuario vuelve a iniciar sesión luego de la aprobación. No hay altas ni aprobaciones administrativas en rutas web.
