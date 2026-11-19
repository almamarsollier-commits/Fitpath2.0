# FitPath 2.0 — Estado de entrega (18/11/2026)

Este resumen corresponde al clon `Fitpath2.0-integracion`, rama `fitpath`. Los
cambios locales siguen sin commit; no se modificaron credenciales ni bases
SQLite durante esta revisión.

## Validación local

- Suite completa: **201/201 pruebas aprobadas**.
- Las pruebas cubren migraciones, checksums, idempotencia, claves foráneas,
  permisos y alcance por rol/sede.
- Python 3.12.16; Flask, Authlib, requests, boto3 y python-dotenv están
  instalados. `pip check` no pudo ejecutarse porque este entorno virtual no
  incluye `pip`; no se reinstalaron dependencias.
- El entorno no tiene Node.js, así que no se repitió una validación JavaScript
  independiente.
- No hay `.env`, bases SQLite ni entornos virtuales versionados. `.env`,
  `.venv/` y `backend/instance/` están ignorados por Git.

## Funcionalidades e integraciones

| Componente | Estado |
| --- | --- |
| Cinco roles y APIs Flask | Implementados; pruebas de autenticación, permisos y aislamiento incluidas. |
| Google Auth | El equipo confirmó flujo OAuth real; no se repitió en esta revisión. |
| AWS S3 | El equipo confirmó carga, lectura privada, reemplazo y eliminación reales; no se repitieron llamadas a AWS. |
| Google Calendar | El equipo confirmó conexión y creación de eventos reales; no se repitió el flujo externo. |
| Mercado Pago | Implementado con pruebas simuladas; falta validar Checkout Pro y Webhooks en sandbox real. |
| Asistente | Motor determinista local; no es IA generativa. Algunas mutaciones siguen deshabilitadas por reglas pendientes. |

Las migraciones 0013 y 0014 están en el worktree. El migrador y las pruebas
verifican integridad referencial, checksums e idempotencia en bases temporales.

## Documentación de entrega y bloqueos

- El PDF `Informe_Segundo_Parcial_FitPath.pdf` existe y tiene cuatro páginas.
  No se pudo extraer su texto en este entorno; su coherencia con el estado
  actual requiere revisión manual.
- Los PDF fuente del SRS y los diagramas citados por `DECISIONES.md` no están
  presentes en `docs/fuentes/`; no fue posible contrastar el código con esos
  originales.
- La rama está 30 commits adelante y 0 detrás de `origin/main` según las refs
  locales. La simulación entre ramas no encontró conflictos; no incluye los
  cambios locales aún sin commit.
- Los archivos están inventariados en el worktree, pero requieren aprobación
  antes de preparar el commit único. No se creó commit, push ni merge.
