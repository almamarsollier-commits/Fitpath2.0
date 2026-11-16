# FitPath 2.0 — Roadmap

**Estado:** borrador actualizado para revisión
**Rama de trabajo:** fitpath
**Alcance:** planificación aprobada para el Bloque 1; no autoriza por sí sola la implementación.

El orden acordado es Bloques 0 a 6. Las 15 decisiones arquitectónicas previas prevalecen en su ámbito. Para requisitos funcionales, el SRS es la fuente principal; Story Mapping y diagramas complementan y ayudan a verificar flujos. Las discrepancias se documentan sin resolverlas por inferencia.

## Bloque 0 — Documentación, arquitectura y planificación

**Objetivo:** dejar acordado el alcance visual inicial y preparar las decisiones de datos para el Bloque 2.

**Entregables**
- Revisión del SRS, Story Mapping, diagramas, AGENTS.md y acuerdos previos.
- Registro de las 15 decisiones arquitectónicas y de las decisiones funcionales aprobadas para el Bloque 1.
- Matriz de funcionalidades del MVP por rol, prioridad, fuente y criterio de aceptación.
- Registro de las contradicciones que afectan el alcance.
- Revisión visual de cardinalidades antes de diseñar la base de datos en el Bloque 2.

**Criterios de finalización**
- El alcance del Bloque 1 y sus criterios quedan reflejados en esta matriz.
- Las decisiones aprobadas y las diferencias documentales están separadas.
- Las cuestiones que no afectan al MVP visual se asignan al bloque correspondiente.
- El usuario revisa y aprueba ROADMAP.md, DECISIONES.md y ESTADO.md.

**Dependencias:** documentación de docs/fuentes/, AGENTS.md y acuerdos aprobados.

## Bloque 1 — MVP visual y funcional con datos simulados

**Objetivo:** ofrecer navegación coherente y funcional para los cinco roles, sin backend real, pagos reales ni integraciones externas.

Todas las filas tienen prioridad **MVP aprobada**; no se establece un orden interno adicional.

| Rol | Funcionalidades | Prioridad | Fuente | Criterio de aceptación |
|---|---|---|---|---|
| Cliente | Dashboard, perfil, objetivos, rutinas, progreso, clases e inscripciones, membresía, consultas de alimentación y pagos. | MVP aprobada | Alcance aprobado; SRS, actor Cliente y RF7–27, RF44–47, RF50; Story Mapping, p. 1; casos de uso. | El selector abre el perfil Cliente. Se pueden consultar y gestionar datos simulados de perfil y objetivos, consultar rutinas y progreso, ver clases/cupos, inscribirse o cancelar sin duplicar ni exceder cupos, consultar historial de asistencia, membresía Gratuita o Premium, alimentación y pagos. No se procesan pagos reales. |
| Entrenador | Dashboard, clientes, rutinas, disponibilidad, clases, asistencia y remuneraciones. | MVP aprobada | Alcance aprobado; SRS, actor Entrenador y RF5–6, RF13–15, RF32–33, RF48–50, RN19–20; Story Mapping, pp. 2–3. | Se consultan clientes y clases asignados; se crean y asignan rutinas simuladas con sus parámetros; se gestionan horarios/disponibilidad; se registra asistencia solo en clases asignadas y para clientes inscriptos; se consultan remuneraciones simuladas. |
| Jefe de sede | Dashboard, empleados, actividades, horarios, cupos y supervisión de su sede. | MVP aprobada | Alcance aprobado; SRS, actor Jefe de sede y RF11, RF14, RF31, RF34–35, RF44–47; Story Mapping, p. 4. | La información visible corresponde a su sede. Se consultan empleados, actividades, inscripciones y disponibilidad; se gestionan actividades, horarios y cupos por Clase. La edición de datos de empleados no se agrega: el SRS establece consulta y Story Mapping sugiere gestión, diferencia registrada en DECISIONES.md. |
| Administrador | Dashboard general, usuarios, roles, sedes, actividades, membresías y supervisión de mantenimiento. | MVP aprobada | Alcance aprobado; SRS, actor Administrador y RF3–4, RF11, RF22, RF28–30, RF36; Story Mapping, pp. 6–7 y 8; casos de uso. | Se gestionan usuarios/roles, sedes, actividades y membresías con datos simulados y se consulta información general. El panel de mantenimiento permite supervisar máquinas y tickets; las modificaciones de estados y tickets corresponden al Técnico. |
| Técnico de mantenimiento | Dashboard, máquinas, tickets, estados e historial. | MVP aprobada | Alcance aprobado; SRS, actor Técnico y RF37–43, RN8–14; Story Mapping, pp. 8–9; casos de uso. | Se consultan máquinas de su sede, se crean y actualizan tickets simulados, se cambia el estado de máquina entre Operativa, En reparación y Fuera de servicio, y se consultan historiales. |

### Criterios comunes del Bloque 1

- Un selector de demostración permite entrar a los cinco roles; no hay autenticación real.
- La navegación funciona entre módulos y presenta solo las acciones visibles del rol.
- La información de sedes y permisos visibles se limita a lo autorizado para el perfil simulado.
- Las acciones actualizan la presentación de datos simulados; no se afirma persistencia entre sesiones.
- La interfaz es responsive, accesible, consistente y se desarrolla con HTML, CSS y JavaScript Vanilla.
- No se conectan backend, base de datos, proveedores de pago ni servicios externos.

**Dependencias:** revisión y aprobación de esta documentación. No hay decisiones funcionales pendientes que bloqueen el MVP visual dentro del alcance descrito.

## Bloque 2 — Base de datos, Flask y APIs REST

**Objetivo:** agregar persistencia y backend para los flujos aprobados.

**Entregables:** modelo relacional revisado visualmente contra los diagramas; esquema compatible con las 15 decisiones arquitectónicas; Flask, SQLite inicial y APIs REST.

**Criterios de finalización**
- Las cardinalidades se verificaron visualmente antes de implementar el esquema.
- El modelo respeta las decisiones aprobadas y no agrega campos o tablas arbitrarios.
- Se validan en backend las reglas de negocio, incluidos cupos, duplicados, pertenencia a Clase y autorización del entrenador.
- Los flujos aprobados usan datos persistentes mediante APIs.
- Se ejecutan las verificaciones existentes pertinentes y se registran sus resultados.

**Dependencias:** cierre del Bloque 1 y revisión visual de los diagramas.

## Bloque 3 — Autenticación y permisos

**Objetivo:** implementar autenticación real y permisos por rol, incluida la integración prevista con Google OAuth.

**Criterios de finalización**
- El acceso y cierre de sesión siguen el flujo aprobado.
- Los permisos se validan en frontend y backend.
- El identificador de acceso y la vinculación de cuentas quedan acordados antes de implementar autenticación.

**Dependencias:** Bloques 2 y decisiones de autenticación previas a este bloque.

## Bloque 4 — Almacenamiento AWS S3

**Objetivo:** incorporar almacenamiento externo para los casos aprobados.

**Criterios de finalización:** casos de uso y roles autorizados definidos; archivos almacenados y recuperados según esa política; credenciales fuera del repositorio.

**Dependencias:** alcance de archivos, permisos, backend y autenticación.

**Avance 2026-11-16:** implementada la imagen privada de perfil del Cliente, con persistencia de clave, autorización, validación y acceso temporal. Pendiente la prueba de conectividad contra el bucket AWS existente.

## Bloque 5 — Integraciones externas, incluido Google Calendar

**Objetivo:** integrar los servicios externos aprobados para sus casos de uso.

**Criterios de finalización:** cada integración tiene datos, permisos y manejo de errores acordados; se verifican sus flujos aprobados.

**Dependencias:** alcance de integración, autenticación y backend.

## Bloque 6 — FitPath Smart Assistant portable

**Objetivo:** incorporar orientación fitness general y acceso conversacional a funciones autorizadas mediante un motor JavaScript Vanilla local, sin modelos, servicios pagos ni conexión obligatoria.

**Criterios de finalización:** base de conocimientos y límites documentados; funcionamiento estático sin Flask; interfaz responsive; consultas reales protegidas por sesión, rol y propiedad; confirmación previa y reglas completas para cualquier mutación; pruebas de conversación, permisos y modo offline.

**Dependencias:** APIs autorizadas para las operaciones reales. Las consultas generales y la demostración estática no dependen del backend.

## Criterio común de salida

Al cerrar cada bloque, informar qué se completó, ejecutar solo verificaciones pertinentes disponibles, registrar pendientes y actualizar documentación relevante. Commits y pushes requieren autorización explícita según AGENTS.md.
