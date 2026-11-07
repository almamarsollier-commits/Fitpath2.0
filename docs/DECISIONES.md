# FitPath 2.0 — Decisiones

**Estado:** borrador actualizado para revisión.
Las decisiones arquitectónicas y funcionales aprobadas se mantienen separadas. Las decisiones previas provienen de acuerdos del proyecto, no se atribuyen al SRS. Las diferencias entre fuentes se registran sin inferir resoluciones no aprobadas.

## 1. Acuerdos arquitectónicos aprobados previamente

Estas 15 decisiones se conservan sin cambios:

1. **USUARIOS:** incorporar apellido y nombreUsuario; mantener fk_rol; eliminar la relación circular fk_administrador.
   **Diferencia:** el ER no muestra apellido ni nombreUsuario y sí muestra fk_administrador.

2. **ACTIVIDAD, CLASE y Horario:** ACTIVIDAD representa el tipo de actividad; CLASE, la sesión programada; Horario será un modelo auxiliar de JavaScript, sin tabla propia.
   **Diferencia:** el ER separa ACTIVIDADES y CLASES; clases incluye Horario; el SRS describe horarios sin fijar este modelo.

3. **RUTINA_EJERCICIO:** incluir series, repeticiones, peso y descanso.
   **Diferencia:** el ER muestra series, repeticiones y descanso, pero no peso; clases muestra series, repeticiones, peso y duración, pero no descanso.

4. **Planes y suscripciones:** MEMBRESIAS almacena planes; CLIENTE_MEMBRESIA registra suscripciones por cliente.
   **Diferencia:** el ER ya muestra ambas entidades; clases separa TipoMembresia y Membresia. El SRS menciona inicialmente Gratuita y Premium.

5. **Objetivos:** mantener OBJETIVOS, TIPO_OBJETIVOS y CLIENTE_OBJETIVO; eliminar la FK inversa innecesaria de TIPO_OBJETIVOS.
   **Diferencia:** el ER muestra esas entidades; sus conexiones deben verificarse visualmente antes de fijar cardinalidades.

6. **Pagos y deudas:** simplificar métodos y estados de pago, y eliminar relaciones circulares entre pagos y deudas, conservando la funcionalidad.
   **Diferencia:** el ER dibuja tablas separadas de métodos y estados; clases usa Pago y Deuda con estados; el SRS no fija ese detalle.

7. **Máquinas:** MAQUINAS incorpora fk_sede.
   **Diferencia:** el SRS dice que la sede del ticket se obtiene mediante el técnico y que la máquina no tiene sede directa; el ER tampoco muestra fk_sede. Se conserva el acuerdo y se registra la discrepancia.

8. **Entrenador y teléfono:** ENTRENADOR incorpora especialidad; el teléfono se centraliza en USUARIOS.
   **Diferencia:** clases muestra especialidad en Entrenador y teléfono en Cliente; el ER no muestra especialidad ni teléfono.

9. **Disponibilidad:** incorporar DISPONIBILIDAD_ENTRENADOR.
   **Diferencia:** clases incluye DisponibilidadEntrenador; el ER no muestra entidad equivalente. El SRS requiere gestionar disponibilidad.

10. **Remuneraciones:** incorporar REMUNERACIONES.
    **Diferencia:** clases incluye Remuneracion y el SRS requiere registrar o consultar remuneraciones; el ER no muestra entidad equivalente.

11. **Permisos:** incorporar PERMISOS y ROL_PERMISO; validar permisos en frontend y backend.
    **Diferencia:** clases incluye Rol y Permiso; el ER muestra ROLES, pero no PERMISOS ni ROL_PERMISO. El SRS exige acceso según rol y permisos.

12. **Reportes:** generarlos inicialmente desde datos existentes, sin exigir tabla independiente.
    **Diferencia:** clases incluye Reporte; el ER no. El SRS requiere reportes sin imponer una tabla.

13. **Atributos:** completar solo los necesarios para representar requisitos aprobados y acuerdos previos; no agregar campos arbitrarios.
    **Diferencia:** los documentos presentan atributos no uniformes; cada atributo futuro debe justificarse por un requisito o acuerdo identificable.

14. **Inscripciones y asistencias:** validar cupos, duplicados, pertenencia a clases y autorización del entrenador.
    **Respaldo y diferencia:** el SRS define límites de cupo, actualización de disponibilidad y autorización del entrenador para asistencia. La prevención de inscripciones duplicadas forma parte del acuerdo previo.

15. **Personalización de rutinas:** utilizar parámetros individuales y observaciones del entrenador.
    **Diferencia:** el SRS requiere personalización y clases incluye observaciones en Rutina; el ER no representa explícitamente las observaciones del entrenador.

## 2. Decisiones funcionales aprobadas para el Bloque 1

Estas ocho decisiones se aprueban para el MVP visual y no modifican los 15 acuerdos arquitectónicos:

1. El acceso inicial utiliza un selector de roles de demostración, sin autenticación real.
2. Los permisos visibles reflejan las responsabilidades de cada rol y su sede.
3. Horarios, cupos e inscripciones pertenecen a cada Clase programada.
4. La interfaz usa los nombres Gratuita y Premium.
5. Alimentación, pagos y remuneraciones muestran datos simulados. No hay pagos reales ni persistencia/integración real en este bloque.
6. Las decisiones arquitectónicas aprobadas prevalecen en su ámbito. Para requisitos funcionales, el SRS es la fuente principal; Story Mapping y diagramas complementan y verifican flujos. Las contradicciones se documentan.
7. La revisión visual detallada de cardinalidades es obligatoria antes de implementar la base de datos en el Bloque 2.
8. El MVP es responsive, accesible, mantiene navegación consistente y usa HTML, CSS y JavaScript Vanilla.

## 3. Aplicación de fuentes y contradicciones relevantes

- **Empleado del Jefe de sede:** el SRS especifica consulta de información del personal; Story Mapping sugiere gestionar sus datos. En el Bloque 1 se incluye consulta de empleados de la sede. No se añade edición de datos de empleados.
- **Mantenimiento del Administrador:** el SRS asigna la operación de tickets y cambios de estado al Técnico; el alcance aprobado incorpora supervisión para el Administrador. El panel de Administración muestra el estado y los tickets; las modificaciones quedan en el perfil Técnico.
- **Nombres de membresía:** el caso de uso menciona Amateur/Pro y el SRS Gratuita/Premium. Para el Bloque 1 prevalece la decisión aprobada Gratuita/Premium; la diferencia de la fuente queda registrada.
- **Identificador de acceso:** SRS, Story Mapping, casos de uso y ER no coinciden entre nombre de usuario y email. No bloquea el Bloque 1 porque no habrá autenticación real. Se resolverá antes del Bloque 3.
- **Clases y cupos:** el modelo aprobado define ACTIVIDAD como tipo y CLASE como sesión; el cupo, horario e inscripción se presentan por Clase. Las cardinalidades físicas se revisan antes del Bloque 2.
- **Alimentación y pagos:** se consultan datos simulados; no se incorporan pagos reales, proveedores, backend ni persistencia en el Bloque 1.

Estas reglas aplican la jerarquía funcional aprobada y el alcance explícito del usuario. No cambian los modelos arquitectónicos previos.

## 4. Pendientes asignados a bloques posteriores

No bloquean el MVP visual:

- Identificador de acceso y vínculo entre cuentas locales y Google OAuth: antes del Bloque 3.
- Alta y asignación de perfiles del personal: antes de implementar autenticación y administración persistente.
- Métodos, estados y proveedor de pagos reales: antes de implementar pagos persistentes.
- Revisión visual de cardinalidades y relaciones de los diagramas: antes del esquema de base de datos del Bloque 2.
- Verificación de concurrencia, tiempos de respuesta y disponibilidad: al definir backend y entorno de ejecución.
- Alcance de archivos en S3, flujos de Calendar y agente de IA: antes de sus respectivos bloques.

## 5. Contexto arquitectónico aprobado en instrucciones previas

- Frontend: HTML semántico, CSS, JavaScript Vanilla con módulos y estilos compartidos en fitpath.css.
- Backend previsto: Python, Flask, SQLite inicial y APIs REST.
- Integraciones previstas para sus bloques: Google OAuth, Google Calendar, AWS S3 y agente de IA personalizado.
- Rama de desarrollo: fitpath; FlaskApi conserva la versión previa; main permanece protegida.
- El orden de bloques es el indicado en ROADMAP.md.

Este contexto proviene de AGENTS.md y acuerdos previos, no de los PDF.

## Fuentes consultadas

- [SRS actualizado](<fuentes/SRS_ProyectoFitPath2.0.pdf>)
- [Story Mapping](<fuentes/Story Mapping FitPath–FigmaMake.pdf>)
- [Diagrama de casos de uso](<fuentes/Diagrama de Caso de Uso.pdf>)
- [Diagrama de clases](<fuentes/Diagrama de clases.pdf>)
- [Diagrama de relaciones entre entidades](<fuentes/Diagrama de RelacionesEntidades FP2.0-2026-11-04-195928.pdf>)

La extracción de texto permite leer etiquetas, entidades y atributos. La ubicación exacta de algunas conexiones y cardinalidades requiere revisión visual y no se infiere aquí.
