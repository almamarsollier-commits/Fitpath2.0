# FitPath 2.0 — Estado del proyecto

**Fecha de revisión:** 2026-11-16
**Repositorio:** C:/Users/marso/OneDrive/Escritorio/Fithpad2.0/Fitpath2.0
**Rama:** feat/google-auth
**Seguimiento remoto:** origin/feat/google-auth

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

## M11 — Entorno recuperado y Google OAuth validado (2026-11-16)

- Se confirmó el clon activo, la rama `feat/google-auth`, HEAD `154bcd06` y sincronización `+0/-0` con `origin/feat/google-auth` antes de los cambios locales.
- El entorno virtual preparado está en `Fithpad2.0/.venv`, no en `.venv` de la raíz. Usa Python 3.15.2, Flask 3.1.3, Authlib 1.9.5 y SQLite 3.53.4. Se instaló `requests==2.34.2`, ya declarado en `requirements.txt`, porque faltaba y Authlib no podía importar.
- El clon no contiene `gimnasio.db`. Las pruebas se corrigieron para comprobar que el archivo heredado permanezca sin cambios cuando existe o continúe ausente en un clon limpio; no se fabricó ni recuperó esa base.
- Se creó la base local ignorada `backend/instance/fitpath-development.sqlite3`. Las migraciones 0001–0009 se aplicaron una vez y la segunda ejecución fue idempotente. `foreign_key_check` devolvió cero filas e `integrity_check` devolvió `ok`.
- El mapa Flask efectivo contiene `/auth/login`, `/auth/google/login`, `/auth/google/callback`, `/auth/me`, `/auth/logout` y `/auth/cliente`.
- El servidor oficial se inició con `backend.fitpath:create_app` en `localhost:5000`. `GET /auth/login` devolvió 200, `GET /auth/me` 401 sin sesión y `GET /auth/cliente` 302 hacia `/auth/login`; el 404 anterior quedó resuelto y se atribuye al servidor/clon antiguo.
- `GET /auth/google/login` generó la redirección OIDC con el callback local configurado. El flujo real completó callback, sesión, `/auth/me` autenticado y dashboard Cliente.
- La solicitud aprobada quedó vinculada exclusivamente a `client1` (ID FitPath 2), activo y con rol y perfil Cliente. `m11_demo_cliente` (ID 1) no recibió una identidad Google.
- El cierre manual registró `POST /auth/logout` con redirección y dos consultas posteriores a `/auth/me` devolvieron 401, confirmando la invalidación de la sesión.
- La regresión completa ejecutó 129 pruebas en 95.357 segundos: `OK`. Incluye OIDC aislado, nonce/state, sesiones, CSRF, logout, rutas Cliente, permisos, migraciones y servicios previos.
- Los PDFs SRS, Story Mapping y diagramas citados por `docs/DECISIONES.md` no están presentes en este clon. Se usaron únicamente los requisitos ya transcritos en la documentación versionada.

## M12 — Autorización incremental (2026-11-15)

- Las vistas Cliente requieren sesión activa, rol `Cliente` consultado desde SQLite y el permiso persistido `cliente.vistas.ver`. El acceso se deniega por defecto si falta cualquiera de los tres controles.
- El nuevo seed de permisos es explícito e idempotente y asigna solo el permiso de las vistas ya implementadas al rol Cliente. No crea usuarios ni amplía accesos a otros roles.
- Las pruebas puntuales aprobaron: 21 de autenticación/autorización y 12 de identidad/permisos.
- Los dashboards y endpoints de Entrenador, Jefe de sede, Administrador y Técnico todavía no existen en el backend actual. No se inventaron permisos para funciones ausentes ni se presentó el panel genérico con datos ficticios como una implementación real.
- `origin/APIs` corresponde al prototipo Express, versiona dependencias y la base heredada, y no contiene autorización Flask reutilizable; no se hizo merge ni se copiaron sus artefactos.

## Bloque 4 — Imagen de perfil privada en AWS S3 (2026-11-16)

- Se aprobó y desarrolló el primer caso S3: el Cliente autenticado puede subir y consultar su propia imagen de perfil desde la API y la interfaz.
- La migración 0010 conserva la clave S3 en `clientes`; la API valida sesión, rol, permiso, propiedad, CSRF, tamaño máximo de 5 MiB y MIME real JPEG/PNG/WebP.
- El servicio existente continúa usando claves opacas, cifrado `AES256`, bucket privado y URLs prefirmadas breves. Al reemplazar una imagen intenta retirar el objeto anterior sin perder la nueva referencia si S3 falla durante esa limpieza.
- Se agregaron pruebas locales de permisos, MIME, errores AWS, aislamiento de propietario y persistencia tras recrear Flask. Se reutilizó el entorno virtual existente de `C:/Proyectos/Fitpath2.0` y se instaló allí `boto3`, ya declarado en `requirements.txt`; la verificación focalizada final de 13 pruebas y la regresión Python completa de 137 pruebas finalizaron en `OK`.
- Node no está disponible en el entorno actual, por lo que no se repitió la suite JavaScript del Asistente de IA; sus tres pruebas API Python sí pasaron dentro de la regresión.
- Tampoco existen bucket, región, perfil AWS, credenciales ni AWS CLI configurados. La comunicación real con AWS continúa pendiente y está documentada en `docs/AWS_S3.md` sin solicitar ni exponer secretos.

## Mercado Pago — Checkout Pro de prueba (2026-11-16)

- La migración 0011 agrega estados de deuda, intentos de pago persistentes y eventos Webhook idempotentes. Los importes, monedas y conceptos se obtienen desde SQLite y el Cliente solo puede iniciar o confirmar pagos vinculados a sus propias deudas.
- Checkout Pro usa la API REST vigente para crear preferencias y consultar cada pago. FitPath exige credenciales declaradas como prueba, utiliza `sandbox_init_point` y rechaza respuestas `live_mode=true`.
- El Webhook valida `x-signature` con HMAC-SHA256 y ventana temporal, registra `x-request-id` y consulta el pago en Mercado Pago antes de cambiar datos. Pago, deuda y posible reactivación de membresía se actualizan dentro de una transacción `BEGIN IMMEDIATE`.
- La pantalla **Membresía** muestra datos persistentes, estados comprensibles, deudas propias, historial y el botón de Checkout Pro. No se agregó SDK ni dependencia: se reutilizó `requests`.
- Existe una carga demo protegida por `--confirm-development-data`, pero no se ejecutó sobre ninguna SQLite porque falta la autorización específica del usuario.
- Las 10 pruebas focalizadas de Mercado Pago finalizaron en `OK`. La primera regresión de 147 pruebas detectó una expectativa visual obsoleta, corregida para distinguir esta vista real en modo de prueba; queda registrada una segunda ejecución completa antes del commit.
- No hay Access Token de prueba, secreto Webhook ni URL pública HTTPS configurados en este entorno. Por lo tanto, no se afirma conectividad real; la configuración y demostración pendiente están documentadas en `docs/MERCADO_PAGO.md`.

## FitPath Smart Assistant — Portable e integrado (2026-11-15)

- Se reemplazó el alcance de IA externa por un motor conversacional determinista en JavaScript Vanilla, sin Ollama, APIs, modelos, plugins, nuevas dependencias ni conexión obligatoria.
- La base estructurada cubre entrenamiento, técnica, recuperación, anatomía básica, nutrición general, macronutrientes, calorías, hidratación y hábitos. Incluye normalización, sinónimos, errores frecuentes, coincidencia aproximada, ambigüedad, contexto reciente y seguimientos.
- El chat flotante se integró en las vistas Cliente y existe una demostración autocontenida en `demo/assistant/index.html` que funciona mediante `file://` sin Flask. En modo offline las operaciones reales se deshabilitan de forma visible.
- La API `/api/v1/assistant` permite consultar clases/cupos, rutina, progreso y membresía propios. Exige sesión, rol Cliente y `cliente.datos.ver`; no recibe un cliente arbitrario ni expone datos ajenos.
- Inscripción y cancelación permanecen deshabilitadas: falta acordar elegibilidad de membresía y no existe servicio de cancelación. No se simulan ni persisten operaciones.
- Edge aprobó nuevamente los 13 escenarios portables. La suite completa aprobó 129 pruebas en 95.357 segundos.
- La arquitectura, modos de ejecución y límites están documentados en `docs/SMART_ASSISTANT.md`.

## Google Calendar — clases del Cliente (2026-11-18)

- Se agregó autorización incremental sin modificar el login OIDC existente. La cuenta autorizante debe coincidir con la identidad Google vinculada al usuario FitPath.
- El Cliente puede añadir únicamente una inscripción propia activa y programada, mediante botón, confirmación y POST protegido por CSRF.
- El evento usa actividad, sede, dirección, inicio, fin y zona horaria persistidos. Un ID determinista de Google y `UNIQUE(inscripcion_id)` evitan duplicados incluso ante reintentos.
- Los refresh tokens quedan cifrados por usuario; el frontend sólo recibe estados de configuración, autorización, éxito o error.
- Las pruebas focalizadas cubren alcance incremental, vínculo de cuenta, cifrado, propiedad, CSRF, datos reales e idempotencia. La conexión real queda pendiente de la configuración detallada en `docs/GOOGLE_CALENDAR.md`.

## Próximo paso

1. Validar AWS S3 contra el bucket privado existente antes de afirmar que la integración externa funciona.
2. Configurar credenciales Mercado Pago de prueba y una URL HTTPS para ejecutar la demostración real de Checkout Pro y Webhooks.
3. Autorizar, si se desea, la carga demo controlada sobre la SQLite de desarrollo.
4. Definir la elegibilidad por membresía y el servicio transaccional de cancelación antes de habilitar mutaciones del asistente.
5. Habilitar Google Calendar API, registrar alcance y callback, configurar el secreto de cifrado y ejecutar la prueba real de creación sin duplicados.

## Actualización para estabilización de entrega (2026-11-18)

Esta sección prevalece sobre los estados pendientes de validación externa
registrados en las entradas históricas anteriores:

- La suite completa del clon `Fitpath2.0-integracion` aprobó 201 pruebas. Se
  cubren APIs de los cinco roles, autenticación, permisos y alcance por sede.
- El equipo reporta pruebas reales satisfactorias de Google Auth, S3 y Google
  Calendar. No se repitieron llamadas externas en esta revisión.
- Mercado Pago continúa con pruebas simuladas; la validación del flujo
  Checkout Pro/Webhooks en sandbox real sigue pendiente.
- No se reprodujeron defectos funcionales que justifiquen cambios de código
  durante esta revisión. La migración y los datos SQLite existentes no se
  modificaron.
- La validación independiente de JavaScript no se ejecutó porque Node.js no
  está disponible en este entorno.
- El PDF del Segundo Parcial tiene cuatro páginas, pero no se pudo extraer su
  texto aquí; requiere cotejo manual con el alcance actual y los diagramas.
- La guía de APIs y las instrucciones de Google Auth se actualizaron para
  reflejar el backend y la ruta `.venv` de este clon.
