# FitPath 2.0

Sistema web de gestión de gimnasios con múltiples sedes y cinco roles: **Cliente, Entrenador, Jefe de sede, Administrador y Técnico de mantenimiento**.

## Tecnologías

- Backend: Python, Flask, APIs JSON, SQLite y migraciones SQL.
- Frontend: HTML5, CSS3 y JavaScript nativo ES6.
- Integraciones: Google OAuth, AWS S3 para fotos privadas, Mercado Pago Checkout Pro (pruebas) y Google Calendar (autorización incremental y eventos por inscripción).

## Requisitos

Python 3.12+, navegador actualizado e instalación de dependencias desde `requirements.txt`. Para funciones externas, credenciales de desarrollo válidas y acceso a los servicios correspondientes. No es necesario instalar Node para ejecutar Flask ni para usar la interfaz web.

## Instalación local en Windows / PowerShell

Desde la carpeta raíz del proyecto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Crear un archivo `.env` **local y no versionado**, tomando los nombres de variables de `docs/GOOGLE_AUTH.md`, `docs/AWS_S3.md`, `docs/MERCADO_PAGO.md` y `docs/GOOGLE_CALENDAR.md`. Nunca agregar tokens ni claves a Git.

```powershell
python -m backend.migrate --environment development
python -m backend.seed --environment development
python apy.py
```

Abrir **http://127.0.0.1:5000/auth/login**. `apy.py` carga `.env`, crea Flask y lo inicia en localhost. El modo depuración incluido es exclusivamente para desarrollo local; no publicar ese servidor directamente en Internet.

Si ya existe el entorno virtual, activarlo en vez de crearlo de nuevo. La aplicación no necesita la rama `origin/APIs`: la implementación de pagos que se utiliza es la de Flask.

## Uso por rol

| Perfil | Operaciones principales |
| --- | --- |
| Cliente | Perfil, reservas, rutinas, progreso, alimentación, membresías, pagos y asistente |
| Entrenador | Alumnos vinculados, rutinas y ejercicios, disponibilidad y asistencia por clase |
| Jefe de sede | Personal, actividades, clases, horarios, cupos y consultas de su sede |
| Administrador | Usuarios, roles, permisos, sedes, membresías, máquinas y reportes |
| Técnico | Máquinas, incidencias, tickets e historial de mantenimiento |

La demostración local utiliza cuentas de prueba solamente cuando `FITPATH_DEMO_LOGIN_ENABLED=1` y se accede desde localhost. No habilitar el modo demo en producción.

## Google Auth

La autenticación OIDC está implementada y el equipo confirmó un flujo real de login, callback, sesión y logout. Configurar el cliente web, la clave de sesión y el URI de retorno exacto según `docs/GOOGLE_AUTH.md`. La identidad Google puede necesitar vinculación con un usuario FitPath ya existente. Esta revisión no repitió el flujo externo.

## Amazon S3

El módulo almacena fotografías de perfil privadas mediante claves opacas, cifrado SSE-S3 y URLs prefirmadas. Configurar `AWS_PROFILE`, `AWS_S3_BUCKET` y `AWS_REGION` en `.env` y conceder exclusivamente acciones de objetos sobre `fitpath/clientes/*`. El equipo reportó una prueba real satisfactoria de carga, consulta, reemplazo y limpieza del bucket privado; no se repitió en esta revisión.

## Google Calendar

La migración `0014_google_calendar.sql` agrega autorizaciones cifradas y asociación de inscripciones con eventos. El Cliente autoriza Calendar separadamente y confirma la creación de cada evento. El equipo confirmó conexión real y creación de eventos desde inscripciones; esta revisión validó el código y los tests locales, pero no repitió la operación externa.

En un entorno nuevo se necesita habilitar Google Calendar API, incorporar el alcance `https://www.googleapis.com/auth/calendar.events.owned`, registrar `http://localhost:5000/auth/google/calendar/callback` como URI autorizado y configurar `GOOGLE_CALENDAR_TOKEN_SECRET` (mínimo 32 caracteres) en el `.env` local. Consultar `docs/GOOGLE_CALENDAR.md`; no compartir ni versionar secretos.

## Mercado Pago

Checkout Pro está implementado exclusivamente para credenciales de prueba, con verificación del proveedor, firma del webhook, idempotencia y persistencia de deuda/pago. La validación conocida es simulada; para una prueba externa se necesitan un Access Token de prueba, URL pública HTTPS, `MERCADOPAGO_CREDENTIAL_SCOPE=test` y secreto de webhook. No usar credenciales ni dinero de producción.

## Pruebas

Desde la raíz del proyecto:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\tests"
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
```

La última ejecución de esta suite en el entorno del proyecto aprobó **201/201 pruebas**. Las pruebas usan bases temporales; para probar migraciones no apuntar a la base local de desarrollo ni a `gimnasio.db`. En este equipo no hay Node.js, por lo que no se ejecutó validación independiente de sintaxis JavaScript.

## Estructura

```text
backend/fitpath/     Factory Flask, configuración, API, autenticación, servicios y migraciones
statics/             CSS global y módulos JS
backend/fitpath/auth/templates/  Login y paneles internos por rol
templates/cliente/   Vistas del Cliente
tests/               Pruebas Python y escenarios JS
docs/                Guías, decisiones, estado y documentación de entrega; los PDF fuente del SRS/diagramas no están en este clon
apy.py               Punto de entrada local
requirements.txt     Dependencias Python
```

## Estado de entrega

Se distinguen **implementación**, **pruebas locales** y **verificación externa reportada**. El equipo confirmó pruebas reales de Google Auth, S3 y Google Calendar; no se repitieron durante esta revisión. Mercado Pago tiene pruebas simuladas y requiere una validación contra su sandbox. El PDF del Segundo Parcial tiene cuatro páginas, pero su contenido no se pudo extraer en este entorno; requiere revisión manual frente al estado actual antes de entregarlo.

Para el Segundo Parcial, adjuntar el PDF de 3–5 páginas, los diagramas actualizados y el proyecto completo. No incluir `.env`, entornos virtuales, bases locales, credenciales ni archivos temporales.
