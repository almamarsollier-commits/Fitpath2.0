# FitPath 2.0 — Estado del proyecto

**Fecha de revisión:** 2026-11-09
**Repositorio:** C:/Proyectos/Fitpath2.0
**Rama:** fitpath
**Seguimiento remoto:** origin/fitpath

## Estado de Git

- Las Microtareas 4, 5 y 6 están publicadas en origin/fitpath; antes de iniciar la Microtarea 7, HEAD y origin/fitpath coincidían en e26fe60f2937a8e57441142512e1824b99fe5c0b.
- docs/referencias-visuales/ permanece sin seguimiento y se conserva intacta.
- Los cambios locales de las Microtareas 7, 8 y 9 permanecen sin commit; se conservan separados por migración y pruebas. docs/referencias-visuales/ sigue sin seguimiento y se conserva intacta.
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

La Microtarea 8 agrega la migración 0007 para técnicos, jefes de sede, máquinas, tickets e historial de mantenimiento. Triggers validan que técnico y máquina coincidan en sede para tickets e historial, y bloquean cambios de sede que invalidarían registros relacionados. No imponen compatibilidad entre rol y perfil ni agregan endpoints o autorización.

Las pruebas M8 usan bases temporales y cubren perfiles, sedes, estados, relaciones, historial, rollback y migraciones acumuladas. La compilación Python y la validación aislada con SQLite de memoria aplicando 0001–0007 fueron satisfactorias, incluyendo triggers, FK e idempotencia. La suite completa se intentó en este entorno, pero no pudo importar sus módulos porque falta Flask (`ModuleNotFoundError`). No se instalaron dependencias. El usuario confirmó después que ejecutó satisfactoriamente la suite acumulada desde VS Code en C:/Proyectos/Fitpath2.0.

La Microtarea 9 agrega la migración 0008 para `remuneraciones`. UNIQUE(clase_id) implementa la cardinalidad aprobada de cero o una fila por clase; el importe se guarda como entero en unidades monetarias menores y la moneda referencia `monedas`. CHECK valida los estados y exige fecha UTC solo para liquidaciones completadas. Triggers bloquean la reasignación del entrenador de una clase con remuneración, el cambio de clase de una remuneración y su eliminación; las anulaciones conservan la fila histórica.

La validación aislada de SQLite con una base temporal aplicó 0001–0008, revisó idempotencia, FK, restricciones, protección histórica y rollback sin errores. La suite completa se intentó en este entorno, pero los módulos no pudieron importarse porque falta Flask (`ModuleNotFoundError`). No se instalaron dependencias. El usuario confirmó después que ejecutó satisfactoriamente la suite acumulada desde VS Code en C:/Proyectos/Fitpath2.0.

Las tablas principales del modelo propuesto están implementadas en las migraciones 0001–0008. Esto no completa el Bloque 2: siguen pendientes reglas de negocio, servicios de aplicación, autenticación/autorización y APIs.

## Decisiones aprobadas y pendientes

Siguen vigentes las 15 decisiones arquitectónicas originales y los acuerdos complementarios. Se suma la decisión aprobada el 2026-11-09: una clase genera como máximo una remuneración, identificada por `UNIQUE(clase_id)`; el entrenador se deriva de la clase y no puede reasignarse después de registrar esa remuneración.

Continúan pendientes: compatibilidad entre rol y perfil; elegibilidad por membresía; autorización del entrenador para registrar asistencia; tratamiento de clases e inscripciones canceladas; pertenencia del objetivo al cliente en rutinas y planes de alimentación; conversión de horarios locales a UTC; solapamientos de disponibilidad; normalización Unicode de nombres de actividades; asignación y autorización entre entrenador y cliente; e identificador de inicio de sesión.

## Próximo paso

La suite acumulada fue confirmada como satisfactoria desde VS Code. Se preparan los commits independientes de M7, M8 y M9; el Bloque 2 conserva reglas, servicios, autenticación/autorización y APIs pendientes.
