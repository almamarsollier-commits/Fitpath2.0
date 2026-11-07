---
name: fitpath-checkpoint
description: "Review completed FitPath features, modules, or development blocks and report verified progress, risks, documentation proposals, and a commit message."
---

# FitPath checkpoint

Usá esta skill cuando el usuario pida revisar un checkpoint al terminar una funcionalidad, módulo o bloque de FitPath. Es una revisión y un informe; no implementes correcciones.

## Límites

- Seguí las instrucciones de `AGENTS.md` y la autorización actual del usuario.
- No cambies de branch. Comprobá que la activa sea `fitpath`; si no, señalalo y no escribas nada.
- No edites ni prepares archivos, no corrijas código, no instales dependencias y no crees documentos.
- Nunca hagas commits, pushes, merges ni operaciones destructivas.
- Conservá cambios preexistentes y distinguí cambios staged, unstaged y sin seguimiento.
- No muestres valores de posibles secretos. No valides credenciales contra servicios externos.

## Revisión

1. Confirma la raíz del repositorio, la branch activa y `git status --short --branch`. Anotá si está sincronizada con su upstream.
2. Identifica archivos agregados, modificados, renombrados y eliminados; diferencia cambios preparados de los no preparados.
3. Inspecciona los cambios pertinentes y su contexto inmediato. Resume únicamente funcionalidad observable en el código; no infieras que algo funciona solo por estar implementado.
4. Consulta `AGENTS.md` y solo la documentación pertinente que exista, como SRS, diagramas, `docs/ESTADO.md`, `docs/ROADMAP.md` y `docs/DECISIONES.md`. Señala contradicciones o requisitos pendientes.
5. Localiza pruebas y verificaciones existentes relevantes. Ejecuta solo las que correspondan al cambio, sin instalarlas ni agregar nuevas. Informa comandos y resultados observados; explica las que no pudieron ejecutarse.
6. Revisa los cambios y nombres de archivo buscando secretos y contenido que no deba versionarse, como `.env`, bases locales, `node_modules`, entornos virtuales, cachés o artefactos generados. Si hay un escáner local disponible, úsalo con redacción completa y sin validación externa; no lo instales. Ante una coincidencia que pueda ser un secreto, informa tipo y ubicación sin mostrar el valor.
7. Propón el texto breve que correspondería a `docs/ESTADO.md`. Propón cambios en `docs/ROADMAP.md` solo si cambió el avance o el alcance acordado, y en `docs/DECISIONES.md` solo si hay una decisión nueva. Si un archivo no existe, indícalo; no lo crees.
8. Sugiere un título y un cuerpo para el commit según la convención de AGENTS.md. Revisá el diff y el contenido antes de proponerlo. El título debe ser breve, descriptivo, en español y empezar con feat:, fix:, delete: o doc:, según corresponda. No uses chore:, tarea: ni otro prefijo sin consultar.
   Incluí en el cuerpo solo las categorías aplicables:
   - Archivos creados: rutas y para qué se agregaron.
   - Archivos modificados: rutas y qué cambió.
   - Archivos eliminados: rutas y por qué se quitaron.
   - Motivo: por qué eran necesarios los cambios.
   No inventes cambios ni menciones rutas ajenas al commit. Podés agrupar muchos archivos generados. Separá propuestas cuando los cambios pertenezcan a tareas distintas. No prepares ni crees el commit.

## Formato de respuesta

Usá siempre estos encabezados y mantené el informe breve:

- **Completado:** funcionalidades realmente implementadas.
- **Verificación:** pruebas o comprobaciones ejecutadas y resultados.
- **Problemas:** errores, riesgos y tareas pendientes.
- **Documentación:** archivos que convendría actualizar y propuesta resumida.
- **Git:** branch, estado, archivos cambiados y mensaje de commit sugerido.
- **Siguiente paso:** una recomendación concreta.
