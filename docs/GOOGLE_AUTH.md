# Google Auth — M11

## Configuración local sin guardar secretos

El backend lee estas variables de entorno:

- `FLASK_SECRET_KEY`: clave aleatoria de Flask, distinta por entorno. Es el nombre preferido.
- `SECRET_KEY`: nombre anterior compatible; se usa sólo cuando `FLASK_SECRET_KEY` no está definido.
- `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`: credenciales del cliente OAuth web.
- `GOOGLE_REDIRECT_URI`: valor opcional; por defecto `http://localhost:5000/auth/google/callback`.

Para conservar la configuración entre ejecuciones, editá el archivo `.env` de
la raíz del repositorio. El archivo está ignorado por Git: actualizá las líneas
existentes sin borrarlo ni compartir su contenido.

```dotenv
FLASK_SECRET_KEY=<clave aleatoria local de al menos 48 caracteres>
GOOGLE_CLIENT_ID=<ID del cliente OAuth de tipo Aplicación web>
GOOGLE_CLIENT_SECRET=<secreto del mismo cliente OAuth>
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/google/callback
```

Podés generar una nueva `FLASK_SECRET_KEY` local sin usar servicios externos:

```powershell
& ".\Fithpad2.0\.venv\Scripts\python.exe" -c "import secrets; print(secrets.token_urlsafe(48))"
```

Pegá el resultado directamente en `.env`; no lo envíes por chat ni lo agregues
a archivos versionados. Si Google entrega credenciales nuevas, copiá sus dos
valores en esas mismas variables y reiniciá Flask.

En Google Cloud Console creá un cliente OAuth de tipo **Aplicación web** y agregá exactamente esta URI en **URIs de redirección autorizados**:

```text
http://localhost:5000/auth/google/callback
```

No hace falta agregar un origen JavaScript para este flujo de servidor. Google permite HTTP en `localhost`; cualquier entorno publicado debe usar HTTPS y su URI exacta. No copies credenciales a este repositorio.

En PowerShell, desde la raíz del clon actual:

```powershell
$python = ".\Fithpad2.0\.venv\Scripts\python.exe"
$env:FLASK_SECRET_KEY = "$(& $python -c 'import secrets; print(secrets.token_urlsafe(48))')"
$env:GOOGLE_CLIENT_ID = "<ID del cliente web>"
$env:GOOGLE_CLIENT_SECRET = "<secreto del cliente web>"
$env:GOOGLE_REDIRECT_URI = "http://localhost:5000/auth/google/callback"
& $python -m backend.migrate --environment development
& $python -m backend.seed --environment development
& $python -m flask --app backend.fitpath:create_app run --host localhost --port 5000
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
& $python -m backend.fitpath.auth.demo
```

El comando es idempotente e informa el ID FitPath. No crea identidad Google ni permisos.

Si la identidad Google verificada aún no está vinculada, se muestra una referencia aleatoria que vence en 15 minutos. El administrador la aprueba localmente, fuera de HTTP:

```powershell
& $python -m backend.fitpath.auth approve --usuario-id 123
```

El comando solicita la referencia sin imprimirla. La tabla guarda únicamente su hash. El usuario vuelve a iniciar sesión luego de la aprobación. No hay altas ni aprobaciones administrativas en rutas web.
