# FitPath 2.0 — Estado del proyecto

**Fecha de revisión:** 2026-11-08
**Repositorio:** C:/Proyectos/Fitpath2.0
**Rama:** fitpath
**Seguimiento remoto:** origin/fitpath

## Estado de Git

- La Microtarea 4 comenzó desde el commit 7c130c94031c3344120b3a22ec83fcf35bbaa71e; fitpath y origin/fitpath estaban sincronizadas.
- docs/referencias-visuales/ ya estaba sin seguimiento y se conserva intacta.
- No se realizó push. El cierre de la Microtarea 4 se registra en commit local.
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

No se implementaron reservas completas, membresías, pagos, autenticación, autorización real ni endpoints privados. La Microtarea 4 ofrece solo una operación interna de inscripción, sin HTTP ni elegibilidad por membresía.

## Decisiones aprobadas y pendientes

Siguen vigentes las 15 decisiones arquitectónicas originales y los acuerdos complementarios. También permanecen registradas las cuatro aprobaciones recientes del modelo.

Continúan pendientes: compatibilidad entre rol y perfil; elegibilidad por membresía; autorización del entrenador para registrar asistencia; tratamiento de clases e inscripciones canceladas; conversión de horarios locales a UTC; solapamientos de disponibilidad; y normalización Unicode de nombres de actividades.

## Próximo paso

La Microtarea 6 fue validada por el usuario y se cierra con este commit local. La Microtarea 7 no se inicia.
