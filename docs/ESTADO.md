# FitPath 2.0 — Estado

**Fecha de revisión:** 2026-11-07
**Repositorio:** C:/Proyectos/Fitpath2.0
**Rama de desarrollo:** fitpath
**Seguimiento remoto:** origin/fitpath

## Estado de Git

- La convención de commits y la planificación del Bloque 0 quedan registradas en dos commits locales doc:, pendientes de publicar.
- El árbol de trabajo contiene cambios visuales sin commit para el Bloque 1; no se realizaron commits ni pushes.
- Los cinco PDF de docs/fuentes/ permanecen físicamente en el clon para consulta local y se excluyen mediante .git/info/exclude hasta completar su revisión visual y de privacidad. No forman parte de los commits.
- No se alteraron main ni FlaskApi. No se modificaron Flask, Express, SQLite, APIs ni OAuth.
- El commit 8e54383 es anterior a la convención nueva; se conserva sin reescribir el historial.

## Configuración y documentación

- AGENTS.md contiene las instrucciones generales de FitPath y la convención obligatoria de commits.
- .agents/skills/fitpath-checkpoint/SKILL.md propone commits de acuerdo con esa convención.
- docs/ROADMAP.md define los bloques 0–6 y el alcance del MVP por rol.
- docs/DECISIONES.md conserva las 15 decisiones arquitectónicas aprobadas e incorpora las 8 definiciones funcionales del Bloque 1.
- docs/fuentes/ contiene localmente el SRS, Story Mapping y los diagramas de casos de uso, clases y relaciones entre entidades. Los PDF quedan excluidos de Git hasta que se revise su publicación.

## Trabajo completado

- Limpieza del seguimiento de node_modules y gimnasio.db, registrada en a57e23b.
- Instrucciones de Codex y skill registradas en 8e54383.
- Convención de commits formalizada en el commit doc: formalizar la convención de commits.
- Planificación del MVP documentada en el commit doc: documentar planificación del MVP de FitPath 2.0.
- Análisis de las fuentes y registro de las 15 decisiones arquitectónicas previas.
- Alcance y decisiones funcionales del Bloque 1 aprobados y reflejados en la documentación.
- Base visual del panel interno con navegación móvil reutilizable.
- Landing pública, panel interno visual y espacio Cliente modular con datos ficticios; las rutas antiguas del Cliente conservan un acceso compatible.
- Recursos deportivos originales generados para uso local; no se enlazan fotografías externas.

## Situación del Bloque 0

La planificación está preparada para revisión final y el MVP visual puede comenzar: contempla los cinco roles, un selector de demostración, datos simulados, navegación y criterios responsive y de accesibilidad. No quedan decisiones funcionales que bloqueen el inicio.

La revisión visual de cardinalidades sigue siendo obligatoria antes del esquema de base de datos del Bloque 2. Las discrepancias documentales relevantes están registradas en DECISIONES.md.

El Bloque 1 está parcialmente implementado. Se completaron la landing pública, el shell visual del panel interno y las vistas modulares demostrativas del Cliente para inicio, actividad, clases y reservas ficticias, rutina, progreso y perfil. Las vistas específicas de Entrenador, Jefe de sede, Administrador y Técnico de mantenimiento siguen pendientes; el panel actual es solo una muestra visual de gestión. El login y el selector de roles demo también siguen pendientes. No hay autenticación, persistencia, reservas reales ni funcionalidades conectadas al backend.

Los perfiles, horarios, métricas, rutinas y reservas visibles en la demostración son ficticios. Los documentos definitivos de privacidad y términos legales siguen pendientes de aprobación y deben completarse antes del lanzamiento público. La demostración no solicita credenciales ni datos personales reales.

## Próximo paso

Revisar visualmente la navegación del espacio Cliente en escritorio y móvil. El login y el selector de roles demo no están implementados. La verificación de cardinalidades documentada en ROADMAP.md y DECISIONES.md sigue siendo obligatoria antes de diseñar la base de datos del Bloque 2.
