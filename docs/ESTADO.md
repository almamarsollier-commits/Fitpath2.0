# FitPath 2.0 — Estado del proyecto

**Fecha de revisión:** 2026-11-08
**Repositorio:** C:/Proyectos/Fitpath2.0
**Rama:** fitpath
**Seguimiento remoto:** origin/fitpath

## Estado de Git

- La rama activa es fitpath; al iniciar esta microtarea no había cambios versionados locales.
- docs/referencias-visuales/ ya estaba sin seguimiento y se conserva intacta.
- Los cambios corresponden a la Microtarea 1; no se incluyeron bases de datos ni dependencias.
- No se instalaron dependencias.

## Estado por bloque

### Bloque 0 — Documentación y planificación

Completado. Las decisiones arquitectónicas y el modelo propuesto están documentados.

### Bloque 1 — MVP visual

Parcialmente implementado. Están disponibles la landing pública, el shell visual del panel interno y el espacio demostrativo del Cliente. Quedan pendientes las vistas específicas de Entrenador, Jefe de sede, Administrador y Técnico de mantenimiento, además del login y selector demo. No hay autenticación ni persistencia real.

### Bloque 2 — Base de datos, Flask y APIs REST

Se agregó código para la infraestructura mínima en backend/: fábrica create_app(), configuración separada de desarrollo y pruebas, conexión SQLite bajo demanda con verificación de PRAGMA foreign_keys y cierre por contexto. La ejecución fue validada por la suite informada por el usuario; este entorno no pudo repetirla.

El módulo de migraciones contiene un runner diseñado para aplicar archivos SQL versionados en transacciones individuales, registrar versión, nombre, checksum e instante UTC, comprobar claves foráneas y revertir una migración fallida. La tabla técnica schema_migrations se crea solo al ejecutar explícitamente el runner. No hay migraciones de negocio, tablas funcionales ni rutas registradas. La suite ejecutada por el usuario ejercitó el runner con bases temporales; no se aplicaron migraciones a la base de desarrollo.

Se agregaron pruebas unittest para la factory, separación de bases, claves foráneas, rechazo de la ruta heredada y rollback de una migración fallida. El usuario reporta que ejecutó la suite desde su terminal de VS Code con Python 3.15.2: 5 pruebas aprobadas, sin errores. Este entorno de Codex no dispone de Python, por lo que el resultado no se repitió aquí.

apy.py, server.js y gimnasio.db no se modificaron ni ejecutaron. El código nuevo incluye una protección para rechazar la ruta exacta de gimnasio.db; la prueba fue aprobada en la suite ejecutada desde VS Code, según el resultado reportado por el usuario. No se crearon archivos de base de datos durante la implementación.

## Decisiones aprobadas y pendientes

Las cuatro decisiones nuevas del esquema —eliminar las dos referencias al administrador, omitir la tabla administradores, iniciar el catálogo de monedas con ARS y aprobar los vocabularios de estado diferenciados— están registradas en docs/DECISIONES.md.

Siguen pendientes: cardinalidad de remuneraciones por clase y duplicados; relación de beneficios con clases o actividades; integridad de rol/perfil ante escrituras directas; e identificador de inicio de sesión para el Bloque 3.

## Próximo paso

La Microtarea 1 queda validada según la ejecución informada por el usuario. La Microtarea 2 no se ha iniciado.
