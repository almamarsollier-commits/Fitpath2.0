# FitPath 2.0 — Guía para desarrollar APIs REST

**Repositorio:** `C:\Proyectos\Fitpath2.0`

**Rama:** `fitpath`

**Estado:** guía de entrega; no implementa endpoints ni autenticación.

## 1. Arquitectura actual

Flask será el backend oficial de FitPath 2.0. La estructura existente separa la creación de la aplicación, la configuración, las conexiones SQLite, las migraciones y los servicios internos:

```text
backend/
  fitpath/
    __init__.py                 fábrica create_app()
    config.py                   configuraciones de desarrollo y pruebas
    database.py                 conexiones get_db() y cierre por contexto
    migrations.py               migrador SQL versionado y checksums
    migrations/                 migraciones 0001–0008
    seeds.py                    datos iniciales aprobados
    services/
      enrollments.py            lógica interna de inscripciones
      payments.py               registro interno de pagos ya realizados
  migrate.py                    comando explícito de migraciones
  seed.py                       comando explícito de seeds
tests/                          pruebas unittest con bases temporales
```

La fábrica todavía no registra blueprints ni endpoints. Las carpetas `api/v1`, `repositories`, `validators` y `models` aún no están implementadas. La base de desarrollo local está en `backend/instance/fitpath-development.sqlite3`, excluida de Git.

## 2. Entorno Python y dependencias

Desde PowerShell, en la raíz del repositorio, se puede preparar un entorno aislado:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install "Flask==3.1.3"
.\.venv\Scripts\python.exe -c "import importlib.metadata; print(importlib.metadata.version('Flask'))"
```

Para iniciar el servidor de desarrollo con la fábrica oficial:

```powershell
python -m flask --app backend.fitpath:create_app run --debug
```

La aplicación aún no registra rutas; un `404` en esta etapa no indica que haya fallado la conexión con la base. El servidor de desarrollo no es un servidor de producción.

Flask es necesario para importar `create_app()`, abrir conexiones con el contexto de aplicación y cargar las pruebas. Las demás funciones actuales usan la biblioteca estándar de Python, incluida `sqlite3`.

`requirements.txt` es una lista heredada sin versiones fijadas: contiene Flask, Authlib, boto3 y python-dotenv. Authlib y python-dotenv aparecen en `apy.py`, que pertenece al prototipo antiguo; boto3 no se usa en el backend actual y queda previsto para una integración futura. No instales el archivo completo sin revisar esas dependencias. `package.json` y `package-lock.json` corresponden al prototipo Express y se conservan temporalmente; no son necesarios para el backend Flask.

La preparación todavía no es completamente reproducible: las dependencias Python no están versionadas. Antes de fijar el entorno de integración continua o producción, el equipo debe revisar y fijar las versiones en una tarea separada.

El backend nuevo lee su configuración desde variables de entorno y no carga `.env`. No guardes claves, tokens ni credenciales en el repositorio; usa variables locales no versionadas o el gestor de secretos del entorno donde se despliegue.

## 3. Base de desarrollo, migraciones y seeds

La ruta predeterminada de desarrollo es `backend/instance/fitpath-development.sqlite3`. `FITPATH_DEV_DATABASE` puede reemplazarla; fijá la ruta de forma explícita en la terminal para evitar apuntar a otra base:

```powershell
$env:FITPATH_DEV_DATABASE = 'C:\Proyectos\Fitpath2.0\backend\instance\fitpath-development.sqlite3'
```

Las migraciones no se ejecutan al crear o iniciar Flask. Se aplican de forma explícita con el migrador existente:

```powershell
python -m backend.migrate --environment development
```

La operación es idempotente y valida el registro/checksums, las claves foráneas y cada migración dentro de su transacción. Los datos iniciales también se cargan explícitamente:

```powershell
python -m backend.seed --environment development
```

El seed aprobado incorpora únicamente los cinco roles funcionales y la moneda ARS con dos decimales. No crea usuarios, contraseñas ni permisos asignados. La base local está excluida de Git. No uses `gimnasio.db` como origen ni destino.

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

**Estado de validación (2026-11-13):** con `.venv` (Python 3.15.2, Flask 3.1.3 y SQLite 3.53.4), `create_app("development")` se importó y creó la aplicación; `get_db()` abrió la base configurada, activó `PRAGMA foreign_keys = 1` y cerró la conexión al terminar el contexto. El registro tiene 0001–0008, `foreign_key_check` está vacío e `integrity_check` devolvió `ok`. Los seeds se importan y su CLI está disponible; la base contiene los cinco roles. La factory todavía no registra rutas ni APIs. El SHA-256 de la base de desarrollo quedó igual antes y después.

## 5. Tablas y servicios existentes

Las migraciones versionadas contienen estas 35 tablas de negocio:

- Identidad y sedes: `roles`, `permisos`, `rol_permiso`, `usuarios`, `sedes`.
- Actividades y clases: `entrenadores`, `entrenador_sede`, `actividades`, `actividad_sede`, `clases`, `disponibilidad_entrenador`.
- Participación: `clientes`, `inscripciones`, `asistencias`.
- Entrenamiento: `tipos_objetivo`, `objetivos`, `cliente_objetivo`, `rutinas`, `ejercicios`, `rutina_ejercicio`.
- Seguimiento y alimentación: `progresos`, `planes_alimentacion`.
- Membresías y pagos: `monedas`, `membresias`, `beneficios`, `membresia_beneficio`, `cliente_membresia`, `deudas`, `pagos`.
- Mantenimiento: `tecnicos_mantenimiento`, `jefes_sede`, `maquinas`, `tickets_mantenimiento`, `historial_mantenimiento`.
- Remuneraciones: `remuneraciones`.

El migrador agrega además la tabla técnica `schema_migrations`.

Servicios internos existentes:

- `create_enrollment(connection, cliente_id, clase_id)` usa una transacción inmediata y comprueba cliente, clase futura programada, actividad habilitada, entrenador vinculado a la sede, duplicados y cupo. No verifica elegibilidad de membresía ni autentica/autoriza al solicitante; no debe publicarse por HTTP todavía.
- `register_completed_payment(...)` registra un pago ya realizado contra una deuda y evita sobrepagos mediante transacción. No procesa dinero ni integra proveedores.

Ninguno de estos servicios está registrado como endpoint.

## 6. Estructura recomendada para `/api/v1`

Crear blueprints versionados y registrar solo los públicos aprobados desde `create_app()`:

```text
backend/fitpath/
  api/
    v1/
      __init__.py               blueprint raíz /api/v1
      public.py                 lecturas públicas no personales
  repositories/                 consultas SQL parametrizadas
  validators/                   validación de requests en servidor
  services/                     reglas de negocio y transacciones
  errors.py                      respuestas de error JSON controladas
```

Las rutas deben limitarse a HTTP y validar los datos recibidos; las consultas van en repositorios y las reglas de dominio/transacciones en servicios. Centralizá el formato de errores sin devolver SQL, trazas ni detalles internos. Añadí pruebas temporales para las respuestas, límites de acceso y validaciones de cada endpoint.

Primeros candidatos públicos, sujetos a definir el contrato: `GET /api/v1/activities` y `GET /api/v1/classes` para actividades ofrecidas y próximas clases. Exponé solo campos públicos expresamente seleccionados, como nombre de actividad, sede pública y horario UTC. La disponibilidad de cupos solo se publica si se aprueba ese dato y se calcula desde `cupo_maximo` e inscripciones; nunca se almacena como contador duplicado.

No expongas nombres de entrenadores, datos de usuarios, emails, teléfonos, inscripciones individuales ni resultados de consultas con `SELECT *` sin una decisión explícita de privacidad. Si el frontend y la API se sirven desde orígenes diferentes, definí una lista de orígenes CORS permitidos; no habilites cualquier origen por defecto.

## 7. Acceso privado, seguridad y pendientes

El selector demo del frontend no autentica ni identifica a una persona. No lo uses para conceder permisos. Hasta implementar autenticación y autorización reales, no publiques operaciones privadas.

La configuración usa variables de entorno; no incluyas secretos en el código ni en Git. Toda entrada se valida en el servidor, cada consulta usa parámetros SQL y los errores HTTP no revelan datos personales ni detalles internos.

Requieren autenticación y autorización por rol, sede y relación con el recurso: perfil y datos de Cliente; rutinas, progreso y alimentación; suscripciones, deudas y pagos; inscripción/cancelación, historial y asistencia; gestión de empleados, máquinas, tickets y remuneraciones. La autorización de Administrador no debe dar acceso indiscriminado a información personal.

Siguen pendientes las decisiones e invariantes de pertenencia de objetivos al cliente, elegibilidad de clases por beneficios, compatibilidad entre roles y perfiles, identidad del entrenador autorizado para asistencia, vinculación entrenador-cliente, cancelaciones, conversión de horarios locales a UTC, solapamientos de disponibilidad y normalización Unicode. También siguen pendientes autenticación real, identificador de acceso, autorización por recurso, gestión de sesiones/credenciales y revisión de privacidad antes de cada respuesta.

`apy.py` y `server.js` pertenecen a prototipos anteriores y no son puntos de entrada del backend oficial. No ejecutes esos servidores ni recuperes su lógica de login. `server.js` conserva rutas antiguas y una conexión a `gimnasio.db`; esa base debe permanecer separada y sin modificaciones. Los templates heredados todavía no se retiraron.

SQLite se usa para desarrollo. Serializa escrituras y no aporta por sí sola alta disponibilidad ni escalado multiinstancia; los requisitos de concurrencia y disponibilidad de producción requieren evaluación antes del despliegue. No se declara completado el Bloque 2: esta guía entrega la infraestructura para iniciar APIs públicas, mientras seguridad y reglas pendientes siguen abiertas.

## 8. Pruebas

Desde la raíz del repositorio y con el intérprete que tiene Flask instalado:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas usan bases temporales y no deben apuntar a `backend/instance/fitpath-development.sqlite3` ni a `gimnasio.db`. El 2026-11-13, `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` ejecutó 96 pruebas en 69.969 segundos: `OK`. La base de desarrollo conservó el mismo SHA-256 antes y después de las verificaciones.

Referencias oficiales: [CLI y detección de fábricas Flask](https://flask.palletsprojects.com/en/stable/cli/), [contexto de aplicación y teardown](https://flask.palletsprojects.com/en/stable/appcontext/) y [servidor de desarrollo](https://flask.palletsprojects.com/en/stable/server/).
