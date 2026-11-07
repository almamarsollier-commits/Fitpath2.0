# FitPath 2.0 — Estado del proyecto

**Fecha de revisión:** 2026-11-07
**Repositorio:** C:/Proyectos/Fitpath2.0
**Rama:** fitpath
**Seguimiento remoto:** origin/fitpath

## Estado de Git

- La rama activa es fitpath y está sincronizada con origin/fitpath al iniciar este checkpoint.
- Las referencias visuales locales de docs/referencias-visuales/ siguen sin seguimiento y no se incluyen en esta entrega.
- Este checkpoint modifica solamente documentación; no cambia otras ramas ni contiene bases locales, dependencias ni código ejecutable.

## Estado por bloque

### Bloque 0 — Documentación y planificación

Completado. La planificación y las decisiones de base están documentadas.

### Bloque 1 — MVP visual

Parcialmente implementado. Están disponibles la landing pública, el shell visual del panel interno y el espacio demostrativo del Cliente. Quedan pendientes las vistas específicas de Entrenador, Jefe de sede, Administrador y Técnico de mantenimiento, además del login y selector demo. No hay autenticación ni persistencia real.

### Bloque 2 — Base de datos, Flask y APIs REST

La arquitectura y el modelo de datos están propuestos en docs/BLOQUE2_BD_PROPUESTA.md y pendientes de aprobación final. Se revisaron los diagramas y se registraron acuerdos complementarios aprobados en docs/DECISIONES.md.

Todavía no existen migraciones SQL ni tablas nuevas implementadas para FitPath 2.0. No se implementaron endpoints nuevos. El backend Flask no fue reorganizado. apy.py, server.js y gimnasio.db permanecen como referencia anterior; no se ejecutaron ni modificaron durante este trabajo. gimnasio.db no forma parte del nuevo modelo.

## Pendientes

- Aprobar o ajustar el esquema propuesto y resolver las decisiones marcadas como pendientes en docs/DECISIONES.md.
- Mantener los datos de prueba aislados de cualquier dato real.
- No habilitar endpoints privados o administrativos antes de implementar autenticación real.
- No afirmar que SQLite cumple los requisitos de concurrencia y disponibilidad del SRS sin mediciones.

## Próximo paso

Mañana: resolver las decisiones abiertas, aprobar el esquema y comenzar la microtarea 1 de la propuesta: estructura Flask, configuración por entorno, conexión SQLite con claves foráneas activas y runner de migraciones.
