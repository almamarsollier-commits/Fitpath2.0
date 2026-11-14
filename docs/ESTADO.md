# FitPath 2.0 — Estado del proyecto

**Fecha de revisión:** 2026-11-11
**Repositorio:** C:/Proyectos/Fitpath2.0
**Rama:** fitpath
**Seguimiento remoto:** origin/fitpath

## Estado de Git

- Las Microtareas 1–9 están implementadas y publicadas en origin/fitpath. Los commits de M7, M8 y M9 son 469b7b3eb31a1f38ea2bc515f1f9694a4067c380, 64c5dff8145c11e42cbb14a4eab4bddaabdc83f8 y 4ea57dce64f47353c0f4b5365297ddb88f68e0f9. HEAD y origin/fitpath coinciden en el commit de M9.
- El commit d80e3286129b06b7127266a97bc72a57a2cbfa15, que elimina statics/js/fitpath.js, fue conservado y aprobado por el usuario; el archivo no se restauró.
- docs/referencias-visuales/ permanece sin seguimiento y se conserva intacta.
- No se instalaron dependencias.

## Estado por bloque

### Bloque 0 — Documentación y plan

Completado. Se conservan las decisiones arquitectónicas originales, los acuerdos aprobados y las decisiones pendientes.

### Bloque 1 — MVP visual

Parcialmente implementado. Están disponibles la landing pública, el shell visual del panel interno y el espacio demostrativo del Cliente. Quedan pendientes las vistas específicas de Entrenador, Jefe de sede, Administrador y Técnico de mantenimiento, además del login y selector demo. No hay autenticación ni persistencia real.

### Bloque 2 — Base de datos, Flask y APIs REST

La Microtarea 1 agregó la infraestructura Flask/SQLite y el migrador versionado. El usuario informó cinco pruebas aprobadas con Python 3.15.2 desde VS Code.

La Microtarea 2 agregó roles, permisos, usuarios y sedes en la migración 0001, y una carga controlada de los cinco roles. El usuario confirmó que las pruebas automatizadas de las Microtareas 1 y 2 se ejecutaron satisfactoriamente desde su terminal de VS Code.

La Microtarea 3 agrega la migración 0002 con entrenadores, entrenador_sede, actividades, actividad_sede, clases y disponibilidad_entrenador. Incluye relaciones compuestas, restricciones para horarios/cupos/estados, índices y triggers que impiden asignar nuevas clases a actividades no habilitadas o entrenadores sin vínculo activo en la sede. Se actualizaron las pruebas de identidad para contemplar el esquema acumulado y se añadió una suite temporal para esta microtarea. No se agregaron inscripciones, asistencias, endpoints ni autenticación.

El usuario confirmó que la suite unittest completa de las Microtareas 1 a 3 se ejecutó satisfactoriamente desde su terminal de VS Code, sin errores. En el entorno de Codex no se pudo importar Flask para repetirla.

La Microtarea 4 agrega la migración 0003 para clientes, inscripciones y asistencias, junto con un servicio interno transaccional de inscripción y pruebas con bases temporales. El servicio comprueba cliente, clase futura programada, actividad habilitada, entrenador activo, duplicados y cupos mediante BEGIN IMMEDIATE. No valida membresías ni autorización de un entrenador autenticado y no tiene endpoint.

El usuario confirmó que la suite automatizada completa de la Microtarea 4 se ejecutó satisfactoriamente desde su terminal de VS Code, sin informar cantidades. En esta sesión no pudo repetirse por la ausencia de Flask; la validación aislada con SQLite y biblioteca estándar comprobó migraciones, transacciones, concurrencia y claves foráneas.

La Microtarea 5 agrega la migración 0004 para tipos_objetivo, objetivos, cliente_objetivo, rutinas, ejercicios y rutina_ejercicio, con FK restrictivas, checks de fecha UTC y parámetros, índices y orden único por rutina. Se añadieron pruebas unittest con bases temporales y se actualizaron las expectativas acumuladas de las Microtareas 2 a 4.

El usuario confirmó que la suite automatizada completa de las Microtareas 1 a 5 terminó satisfactoriamente desde su terminal de VS Code. En este entorno no pudo repetirse porque falta Flask; no se instalaron dependencias. Una validación aislada con sqlite3 verificó la aplicación e idempotencia de las migraciones 0001–0004, claves foráneas, checks y rollback de una migración fallida. El tamaño y la fecha de modificación de gimnasio.db no cambiaron.

Queda pendiente decidir si rutinas.objetivo_id debe corresponder a una fila de cliente_objetivo del mismo cliente y cómo asegurar en el futuro la autorización real del entrenador. No se agregó una relación entrenador-cliente ni endpoints.

La Microtarea 6 agrega la migración 0005 con progresos y planes_alimentacion. Conserva mediciones históricas por cliente y planes con objetivo requerido según el modelo aprobado; añade indicaciones opcionales por el requisito explícito de esta microtarea. No crea servicios, autenticación ni endpoints.

La FK de plan a objetivo no garantiza pertenencia a cliente_objetivo para el mismo cliente; esa decisión sigue pendiente. Se añadieron pruebas con bases temporales para integridad, rangos, historia, idempotencia y rollback.

El usuario confirmó que ejecutó satisfactoriamente desde VS Code la suite completa: python -m unittest discover -s tests -v. En este entorno no pudo repetirse porque falta Flask; no se instalaron dependencias. La validación aislada con sqlite3 comprobó la migración 0005, relaciones, rangos, historial, idempotencia y rollback. La sintaxis de las pruebas compiló correctamente y gimnasio.db no cambió en tamaño ni fecha de modificación.

SQLite verifica el formato canónico UTC y el orden de inicio/fin. La conversión entre la zona horaria IANA de la sede, UTC, disponibilidad semanal y conflictos horarios requiere lógica de servicio. La base tampoco impone solapamientos entre disponibilidades. La compatibilidad entre usuarios.rol_id y el perfil Entrenador permanece pendiente; la FK de entrenadores solo verifica que exista el usuario.

apy.py, server.js y gimnasio.db no se modificaron ni ejecutaron. Las pruebas usan bases temporales; la nueva migración opera sobre la conexión que recibe y conserva las relaciones históricas con ON DELETE RESTRICT.

Antes de la Microtarea 7 no había persistencia de membresías ni pagos. La Microtarea 4 ofrece solo una operación interna de inscripción, sin HTTP ni elegibilidad por membresía. No se implementa autenticación, autorización real ni endpoints privados.

La Microtarea 7 agrega la migración 0006 para monedas, membresías, beneficios, suscripciones de clientes, deudas y pagos. La relación membresía-beneficio es genérica y no determina qué clases o actividades habilita. El seed controlado incorpora únicamente ARS con dos decimales; no crea planes con precios ni beneficios comerciales.

Se agregó un servicio interno que registra pagos ya realizados, suma únicamente los pagos confirmados y rechaza importes que superen el saldo dentro de `BEGIN IMMEDIATE`. No cobra, no integra proveedores, no cambia pagos pendientes/anulados y no se expone por HTTP. Requiere autenticación y autorización antes de cualquier uso desde una interfaz.

El usuario confirmó que la suite completa de M7 terminó satisfactoriamente desde VS Code. En este entorno no pudo repetirse porque falta Flask. La compilación y validación aislada con SQLite de memoria comprobaron migraciones, FK, pagos parciales, concurrencia, rollback e idempotencia.

La Microtarea 8 agrega la migración 0007 para técnicos, jefes de sede, máquinas, tickets e historial de mantenimiento. Triggers validan que técnico y máquina coincidan en sede para tickets e historial, y bloquean cambios de sede que invalidarían registros relacionados. No imponen compatibilidad entre rol y perfil ni agregan endpoints o autorización. Su commit está publicado en origin/fitpath.

Las pruebas M8 usan bases temporales y cubren perfiles, sedes, estados, relaciones, historial, rollback y migraciones acumuladas. La compilación Python y la validación aislada con SQLite de memoria aplicando 0001–0007 fueron satisfactorias, incluyendo triggers, FK e idempotencia. La suite completa se intentó en este entorno, pero no pudo importar sus módulos porque falta Flask (`ModuleNotFoundError`). No se instalaron dependencias. El usuario confirmó después que ejecutó satisfactoriamente la suite acumulada desde VS Code en C:/Proyectos/Fitpath2.0.

La Microtarea 9 agrega la migración 0008 para `remuneraciones`. UNIQUE(clase_id) implementa la cardinalidad aprobada de cero o una fila por clase; el importe se guarda como entero en unidades monetarias menores y la moneda referencia `monedas`. CHECK valida los estados y exige fecha UTC solo para liquidaciones completadas. Triggers bloquean la reasignación del entrenador de una clase con remuneración, el cambio de clase de una remuneración y su eliminación; las anulaciones conservan la fila histórica. Su commit está publicado en origin/fitpath.

La validación aislada de SQLite con una base temporal aplicó 0001–0008, revisó idempotencia, FK, restricciones, protección histórica y rollback sin errores. La suite completa se intentó en este entorno, pero los módulos no pudieron importarse porque falta Flask (`ModuleNotFoundError`). No se instalaron dependencias. El usuario confirmó después que ejecutó satisfactoriamente la suite acumulada desde VS Code en C:/Proyectos/Fitpath2.0.

Las tablas principales del modelo propuesto están implementadas en las migraciones 0001–0008. Esto no completa el Bloque 2: siguen pendientes reglas de negocio, servicios de aplicación, autenticación/autorización y APIs.

## Consolidación de la base de desarrollo (2026-11-11)

- Se creó `backend/instance/fitpath-development.sqlite3` luego de confirmar que no existía, que estaba separada de `gimnasio.db` y que `/backend/instance/` está excluida de Git.
- El entorno no tiene Flask. Para no instalar dependencias, se invocaron directamente las funciones existentes `apply_migrations()` y `seed_initial_roles()` / `seed_initial_currencies()` desde Python estándar; no se creó otro migrador. La primera ejecución aplicó 0001–0008; la segunda no aplicó cambios. Se registraron las ocho versiones.
- Verificaciones SQLite: claves foráneas activas en la conexión de migración; `foreign_key_check` vacío; `integrity_check` correcto; existen las 35 tablas de negocio y `schema_migrations` (36 tablas en total). El seed contiene solo los cinco roles aprobados y ARS con dos decimales; no hay usuarios, permisos ni asignaciones de permisos.
- `gimnasio.db` se inspeccionó en modo de solo lectura: contiene `socios` y `usuarios`, su integridad es correcta y su tamaño y fecha de modificación no cambiaron.
- La inspección estática confirma que `create_app()` no abre la base, no ejecuta migraciones ni seeds y no registra blueprints; la conexión está diseñada para abrirse bajo demanda y cerrarse al finalizar el contexto. También rechaza la ruta de `gimnasio.db`. En la reverificación de cierre, la importación de `create_app()` falló porque Flask no está instalado en el Python del sistema ni en `.venv`; la conexión real y el cierre por contexto quedan sin validar en este entorno.
- Se reabrió la base de desarrollo en solo lectura: contiene las versiones 0001–0008, `PRAGMA foreign_key_check` no encontró inconsistencias y `PRAGMA integrity_check` devolvió `ok`. Esta comprobación no valida la conexión Flask.
- `python -m unittest discover -s tests -v` no pudo importar las pruebas porque falta Flask (`ModuleNotFoundError`); los módulos detectados fallaron durante la carga, por lo que no se considera aprobada ni ejecutada la suite funcional. Los tests existentes usan directorios temporales. No se instalaron dependencias.
- No se implementaron APIs ni autenticación. `apy.py` y `server.js` no se ejecutaron ni modificaron. La integración de Flask y la suite completa quedan pendientes de validación en un entorno con los requisitos instalados.
- Los archivos heredados identificados siguen conservados: `apy.py`, los cuatro templates antiguos, `statics/js/modules/cliente.js`, `templates/cliente.html`, `server.js`, `gimnasio.db` y las configuraciones/dependencias. `statics/js/fitpath.js` permanece eliminado por decisión aprobada. No se realizó la limpieza porque Flask y la suite no pudieron validarse en este entorno.
- Las APIs REST públicas quedan a cargo de otro colaborador y deben desarrollarse sobre la fábrica Flask nueva. Autenticación y autorización reales continúan pendientes; el selector demo no concede permisos.

## Verificación final de M10 (2026-11-13)

- El `.venv` del repositorio usa Python 3.15.2. Flask faltaba en ese entorno; se instaló solo `Flask==3.1.3`, ya declarado en `requirements.txt` y verificado compatible con esta versión de Python. El manifiesto no se modificó y mantiene dependencias sin versiones fijadas.
- `create_app("development")` y la conexión Flask real fueron validados. La ruta efectiva es `backend/instance/fitpath-development.sqlite3`; cada conexión activa claves foráneas y el teardown la cierra. Las migraciones 0001–0008 estaban aplicadas; no se reaplicaron. `foreign_key_check` no reportó filas y `integrity_check` devolvió `ok`.
- Los cinco roles están cargados; las funciones de seed y `python -m backend.seed --help` están disponibles. La factory no registra rutas todavía.
- `python -m unittest discover -s tests -v`: 96 pruebas, 69.969 s, `OK`. Los tests usan bases temporales. El SHA-256 de la base de desarrollo permaneció idéntico; `gimnasio.db` no se abrió ni modificó.
- `backend` no importa ni inicia `apy.py` o `server.js`; `database.py` rechaza `gimnasio.db` y la suite comprueba esa protección. Los tres prototipos se conservaron.
- En el backend activo no hay rutas OAuth, configuración Google ni `.env`; Authlib figura en el manifiesto, pero no se utiliza. No se implementaron APIs, OAuth, frontend ni cambios de esquema.

## Decisiones aprobadas y pendientes

Siguen vigentes las 15 decisiones arquitectónicas originales y los acuerdos complementarios. Se suma la decisión aprobada el 2026-11-09: una clase genera como máximo una remuneración, identificada por `UNIQUE(clase_id)`; el entrenador se deriva de la clase y no puede reasignarse después de registrar esa remuneración.

Continúan pendientes: compatibilidad entre rol y perfil; elegibilidad por membresía; autorización del entrenador para registrar asistencia; tratamiento de clases e inscripciones canceladas; pertenencia del objetivo al cliente en rutinas y planes de alimentación; conversión de horarios locales a UTC; solapamientos de disponibilidad; normalización Unicode de nombres de actividades; asignación y autorización entre entrenador y cliente; e identificador de inicio de sesión.

## Próximo paso

El primer paso pendiente es completar la verificación real de M11 descrita a continuación. No declarar la autenticación integrada hasta que el servidor Flask efectivo sirva las rutas nuevas y el flujo sea comprobado en Chrome.

## M11 — Pendiente de verificación real (2026-11-14)

- Google Auth permitió autenticar la cuenta y vincularla al usuario FitPath ID 1, rol Cliente.
- `GET /auth/me` devolvió `authenticated: true` para esa sesión.
- La suite completa anterior informó 111 pruebas aprobadas.
- Las últimas seis pruebas puntuales de integración de acceso al Cliente, navegación, autorización y logout aprobaron.
- Se implementó `/auth/cliente`, las vistas Cliente protegidas por sesión y rol, y el logout POST con CSRF.
- **Bloqueo real: `/auth/cliente` todavía devuelve HTTP 404 en el servidor `localhost:5000`.**
- Se detectaron procesos Flask antiguos sin recarga automática; no se confirmó que el servidor efectivo utilice este checkout.
- El acceso visual al dashboard Cliente y el logout real en Chrome todavía no están verificados.
- La suite completa de 111 pruebas no se repitió tras la integración de las vistas Cliente; los cambios posteriores se validaron con las seis pruebas puntuales mencionadas.
- M11 no debe declararse completamente terminada hasta resolver el 404 y completar la comprobación visual y de logout.

### Recuperación al retomar

1. Confirmar carpeta, intérprete y proceso que escucha el puerto 5000.
2. Comparar `flask routes` con las rutas del servidor efectivo.
3. Corregir exclusivamente la causa del 404.
4. Probar el panel Cliente, el logout y que `/auth/me` devuelva 401 después del logout.
5. Continuar con M12, AWS S3 y el asistente de IA.
