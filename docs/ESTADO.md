# FitPath 2.0 — Estado del proyecto

**Fecha de revisión:** 2026-11-08
**Repositorio:** C:/Proyectos/Fitpath2.0
**Rama:** fitpath
**Seguimiento remoto:** origin/fitpath

## Estado de Git

- La Microtarea 3 comenzó desde el commit ff9ebb520e7b55a03397799e795f7d7e02aec95d, publicado en origin/fitpath.
- docs/referencias-visuales/ ya estaba sin seguimiento y se conserva intacta.
- No se realizó push durante esta microtarea.
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

SQLite verifica el formato canónico UTC y el orden de inicio/fin. La conversión entre la zona horaria IANA de la sede, UTC, disponibilidad semanal y conflictos horarios requiere lógica de servicio. La base tampoco impone solapamientos entre disponibilidades. La compatibilidad entre usuarios.rol_id y el perfil Entrenador permanece pendiente; la FK de entrenadores solo verifica que exista el usuario.

apy.py, server.js y gimnasio.db no se modificaron ni ejecutaron. Las pruebas usan bases temporales; la nueva migración opera sobre la conexión que recibe y conserva las relaciones históricas con ON DELETE RESTRICT.

No se implementaron inscripciones, asistencias, reservas, membresías, pagos, autenticación, autorización real ni endpoints privados.

## Decisiones aprobadas y pendientes

Siguen vigentes las 15 decisiones arquitectónicas originales y los acuerdos complementarios. También permanecen registradas las cuatro aprobaciones recientes del modelo.

Continúan pendientes: compatibilidad entre rol y perfil Entrenador; conversión entre horarios locales y UTC; solapamientos de disponibilidad; tratamiento de clases futuras al desactivar un entrenador de una sede; y normalización Unicode de nombres de actividades. También siguen pendientes las decisiones sobre remuneraciones por clase, beneficios de membresías e identificador de inicio de sesión.

## Próximo paso

La Microtarea 3 fue validada y cerrada con commit local; la siguiente microtarea no se inició.
