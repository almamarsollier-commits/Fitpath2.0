# FitPath 2.0 — Estado del proyecto

**Fecha de revisión:** 2026-11-08
**Repositorio:** C:/Proyectos/Fitpath2.0
**Rama:** fitpath
**Seguimiento remoto:** origin/fitpath

## Estado de Git

- La Microtarea 2 comenzó desde el commit 958df4dd21e16221537cc06e4225e996bcc5cbce; al inicio, fitpath y origin/fitpath estaban sincronizadas.
- docs/referencias-visuales/ ya estaba sin seguimiento y se conserva intacta.
- No se realizaron commits ni pushes.
- No se instalaron dependencias.

## Estado por bloque

### Bloque 0 — Documentación y plan

Completado. Se conservan las decisiones arquitectónicas originales, los acuerdos aprobados y las decisiones pendientes.

### Bloque 1 — MVP visual

Parcialmente implementado. Están disponibles la landing pública, el shell visual del panel interno y el espacio demostrativo del Cliente. Quedan pendientes las vistas específicas de Entrenador, Jefe de sede, Administrador y Técnico de mantenimiento, además del login y selector demo. No hay autenticación ni persistencia real.

### Bloque 2 — Base de datos, Flask y APIs REST

La Microtarea 1 agregó la infraestructura Flask/SQLite, la factory create_app(), configuraciones separadas, conexión bajo demanda con PRAGMA foreign_keys, y un migrador SQL versionado con registro de versión, checksum, transacción por migración y comprobación referencial. Su suite de cinco pruebas fue ejecutada por el usuario desde VS Code con Python 3.15.2 y aprobada.

La Microtarea 2 agrega la migración 0001_identidad_roles_permisos_sedes.sql con las tablas roles, permisos, rol_permiso, usuarios y sedes. Incluye claves foráneas, restricciones e índices. Los cinco roles tienen una carga idempotente separada. Puede invocarse con python -m backend.seed --environment development o python -m backend.seed --environment testing; no se cargan usuarios ni permisos y no hay endpoints registrados.

Se agregó una suite específica para estas tablas, que usa bases temporales y cubre relaciones, unicidad, validaciones, seed, checksums, rollback, aislamiento de entornos y protección de gimnasio.db. El usuario confirmó que las pruebas automatizadas de las Microtareas 1 y 2 se ejecutaron satisfactoriamente desde su terminal de VS Code; no se consigna un conteo para la suite combinada porque no fue informado. En esta sesión Codex no ejecutó la suite completa por falta de Flask en su intérprete. Una validación separada con SQLite y bases temporales confirmó esquema, claves foráneas, seed, idempotencia, unicidad, rollback y checksum.

El esquema persiste nombres de usuario y emails recortados y en minúscula ASCII. La collation NOCASE y lower() incorporados en SQLite solo cubren ASCII; la normalización Unicode NFC/casefold debe aplicarse en el servidor cuando existan escrituras y autenticación. El identificador de inicio de sesión sigue pendiente.

apy.py, server.js y gimnasio.db no se modificaron ni ejecutaron. El backend nuevo conserva la protección que rechaza la ruta exacta de gimnasio.db; las nuevas pruebas incluyen una comprobación de metadatos antes y después del rechazo. No se crearon bases locales dentro del repositorio.

No se implementaron perfiles, autenticación, permisos efectivos, endpoints sensibles ni tablas de clases, membresías, pagos o remuneraciones.

## Decisiones aprobadas y pendientes

Siguen vigentes las 15 decisiones arquitectónicas originales y los acuerdos complementarios. También están registradas las cuatro aprobaciones más recientes: omitir referencias y tabla de administradores, iniciar moneda con ARS y conservar vocabularios de estados diferenciados.

Continúan pendientes las decisiones sobre remuneraciones por clase, beneficios de membresías, compatibilidad de roles y perfiles ante escrituras directas, e identificador de inicio de sesión para el Bloque 3. No se cerraron mediante esta microtarea.

## Próximo paso

La Microtarea 2 quedó validada por el usuario y está lista para registrar en un commit local. La Microtarea 3 no se inició.
