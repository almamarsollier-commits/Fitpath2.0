# FitPath 2.0 — Guía para desarrollar APIs REST

**Repositorio:** `Fitpath2.0-integracion`

**Rama:** `fitpath`

**Estado:** actualización al 2026-11-18. Esta guía describe el backend Flask
actual; las secciones de diseño anteriores que contradigan este estado quedan
obsoletas.

## 1. Arquitectura actual

Flask será el backend oficial de FitPath 2.0. La estructura existente separa la creación de la aplicación, la configuración, las conexiones SQLite, las migraciones y los servicios internos:

```text
backend/
  fitpath/
    __init__.py                 fábrica create_app()
    config.py                   configuraciones de desarrollo y pruebas
    database.py                 conexiones get_db() y cierre por contexto
    migrations.py               migrador SQL versionado y checksums
    migrations/                 migraciones 0001–0014
    api/v1/                     blueprints REST por dominio y rol
    auth/                       login Google, sesiones, permisos y vistas por rol
    seeds.py                    datos iniciales aprobados
    services/
      enrollments.py            inscripciones y validación de membresía
      google_calendar.py        autorización y eventos por inscripción
      payment_intents.py        Checkout Pro y conciliación
      s3_storage.py             imágenes privadas de perfil
  migrate.py                    comando explícito de migraciones
  seed.py                       comando explícito de seeds
tests/                          pruebas unittest con bases temporales
```

`create_app()` registra los blueprints de autenticación, vistas y API v1. No
existen carpetas `repositories`, `validators` ni `models`; las consultas
parametrizadas y validaciones viven en los módulos actuales de API/servicios.
La base de desarrollo predeterminada está en
`backend/instance/fitpath-development.sqlite3`, excluida de Git.

## 2. Entorno Python y dependencias

Desde PowerShell, en la raíz del repositorio, se puede preparar un entorno aislado:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -c "import importlib.metadata; print(importlib.metadata.version('Flask'))"
```

Para iniciar Flask en desarrollo, cargar `.env` y abrir el login:

```powershell
.\.venv\Scripts\python.exe apy.py
```

Abrir `http://127.0.0.1:5000/auth/login`. `apy.py` es el punto de entrada
oficial y limita el servidor de depuración a localhost; no usarlo en producción.

`requirements.txt` contiene Flask, Authlib, requests, boto3, python-dotenv y
tzdata. Authlib y requests están versionados; las demás dependencias no tienen
versión fijada. `package.json` corresponde al prototipo Express y no es
necesario para ejecutar la aplicación Flask. No ejecutar `npm test` como
validación del backend.

`apy.py` carga el `.env` local antes de crear la app. El backend también recibe
configuración desde variables de entorno. No guardes claves, tokens ni
credenciales en el repositorio; usa variables locales no versionadas o el
gestor de secretos del entorno.

## 3. Base de desarrollo, migraciones y seeds

La ruta predeterminada de desarrollo es `backend/instance/fitpath-development.sqlite3`. `FITPATH_DEV_DATABASE` puede reemplazarla; fijá la ruta de forma explícita en la terminal para evitar apuntar a otra base:

```powershell
$env:FITPATH_DEV_DATABASE = "$PWD\backend\instance\fitpath-development.sqlite3"
```

Las migraciones no se ejecutan al crear o iniciar Flask. Se aplican de forma explícita con el migrador existente:

```powershell
python -m backend.migrate --environment development
```

Antes de ejecutar migraciones sobre una base existente, realizar un respaldo
local. La operación es idempotente y valida el registro/checksums, las claves
foráneas y cada migración dentro de su transacción. Los datos iniciales también
se cargan explícitamente:

```powershell
python -m backend.seed --environment development
```

Los seeds incorporan los cinco roles, permisos explícitos para vistas y datos por rol, y la moneda ARS con dos decimales. No crean usuarios ni contraseñas. La base local está excluida de Git. No uses `gimnasio.db` como origen ni destino.

## 4. Obtener una conexión SQLite en Flask

`get_db()` requiere un contexto de aplicación. Abre la conexión bajo demanda; `database.py` activa y comprueba `PRAGMA foreign_keys` en cada conexión. El teardown de la aplicación llama a `close_db()` al cerrar el contexto:

```python
from backend.fitpath import create_app
from backend.fitpath.database import get_db

app = create_app("development")

with app.app_context():
    db = get_db()
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    rows = db.execute(
        "SELECT id_actividad, nombre FROM actividades WHERE nombre = ?",
        ("Funcional",),
    ).fetchall()
```

Usá parámetros (`?`) para todo valor dinámico. No interpolés valores del request dentro del SQL. No conserves conexiones globales ni uses `gimnasio.db`; `connect_database()` rechaza explícitamente esa ruta.

**Validación actual:** la suite usa bases temporales y cubre migraciones,
claves foráneas, checksums, permisos y rutas por rol. La última ejecución
completa registrada aprobó 201 pruebas el 2026-11-18; no se usó la base local
durante esa ejecución.

## 5. Tablas y servicios existentes

Las migraciones 0001–0014 contienen el esquema de negocio de identidad, sedes,
clases, inscripciones, perfiles, seguimiento, membresías, pagos, mantenimiento,
Google y Calendar. La lista detallada de entidades aprobadas está en
`docs/BLOQUE2_BD_PROPUESTA.md`; las migraciones 0013 y 0014 incorporan además
rutinas activas y las dos tablas de Google Calendar.

- Identidad y sedes: `roles`, `permisos`, `rol_permiso`, `usuarios`, `sedes`.
- Actividades y clases: `entrenadores`, `entrenador_sede`, `actividades`, `actividad_sede`, `clases`, `disponibilidad_entrenador`.
- Participación: `clientes`, `inscripciones`, `asistencias`.
- Entrenamiento: `tipos_objetivo`, `objetivos`, `cliente_objetivo`, `rutinas`, `ejercicios`, `rutina_ejercicio`.
- Seguimiento y alimentación: `progresos`, `planes_alimentacion`.
- Membresías y pagos: `monedas`, `membresias`, `beneficios`, `membresia_beneficio`, `cliente_membresia`, `deudas`, `pagos`.
- Mantenimiento: `tecnicos_mantenimiento`, `jefes_sede`, `maquinas`, `tickets_mantenimiento`, `historial_mantenimiento`.
- Remuneraciones: `remuneraciones`.

El migrador agrega además la tabla técnica `schema_migrations`.

Servicios actuales incluyen:

- Inscripciones, rutinas, progreso, alimentación y membresías del Cliente.
- Gestión de rutinas, ejercicios, disponibilidad y asistencias del Entrenador.
- Gestión de personal, actividades y clases limitada a la sede del Jefe de sede.
- Gestión administrativa de usuarios, sedes, roles, permisos, membresías y reportes.
- Tickets, máquinas e historial con acceso limitado al Técnico de su sede.
- Pagos, imagen S3 y Google Calendar sujetos a sus permisos y validaciones.

## 6. Blueprints actuales de `/api/v1`

La API v1 está implementada por dominios:

```text
api/v1/account_profile.py   perfil autenticado
api/v1/client.py            clases, inscripciones, rutinas, progreso y alimentación
api/v1/trainer.py           rutinas, disponibilidad y asistencias
api/v1/manager.py           personal, actividades y clases de sede
api/v1/admin.py             usuarios, sedes, catálogos, permisos e informes
api/v1/technician.py        máquinas y mantenimiento
api/v1/payments.py          membresías, pagos y webhook
api/v1/calendar.py          estado y eventos de Google Calendar
api/v1/assistant.py         consultas protegidas del Cliente
```

Los endpoints privados validan sesión, rol, permiso y pertenencia al recurso;
los de escritura aplican CSRF cuando corresponde. No se habilitó CORS abierto.
Los tests de API verifican respuestas, propiedad de datos y restricciones de
rol/sede.

## 7. Acceso privado, seguridad y pendientes

El login real y las sesiones Flask están implementados. El acceso demo es una
función separada y limitada a desarrollo local; no sustituye OAuth ni concede
permisos por sí mismo.

La configuración usa variables de entorno; no incluyas secretos en el código ni en Git. Toda entrada se valida en el servidor, cada consulta usa parámetros SQL y los errores HTTP no revelan datos personales ni detalles internos.

La autorización de Administrador no concede acceso indiscriminado a
información personal. Las pruebas cubren separación por rol y sede. Permanecen
pendientes las decisiones de negocio registradas en `docs/DECISIONES.md`,
incluida la elegibilidad detallada de beneficios y las mutaciones del asistente
que no cuentan con reglas aprobadas.

`apy.py` es el punto de entrada Flask actual. `server.js` corresponde a un
prototipo Express heredado y no es necesario para iniciar FitPath; su base
`gimnasio.db` permanece separada y no debe usarse con el backend actual.

SQLite está configurada para desarrollo. Alta disponibilidad y escalado
multiinstancia requieren evaluación antes de producción.

## 8. Pruebas

Desde la raíz del repositorio y con el intérprete que tiene Flask instalado:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\tests"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas usan bases temporales y no deben apuntar a
`backend/instance/fitpath-development.sqlite3` ni a `gimnasio.db`. El
2026-11-18 se ejecutaron 201 pruebas: `OK`.

Referencias oficiales: [CLI y detección de fábricas Flask](https://flask.palletsprojects.com/en/stable/cli/), [contexto de aplicación y teardown](https://flask.palletsprojects.com/en/stable/appcontext/) y [servidor de desarrollo](https://flask.palletsprojects.com/en/stable/server/).
