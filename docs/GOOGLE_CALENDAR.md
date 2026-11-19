# Google Calendar — configuración y validación

El equipo confirmó conexión real, autorización del Cliente y creación de
eventos desde inscripciones. Esta revisión no repitió el flujo externo; las
pruebas automatizadas locales verifican reglas, permisos, cifrado e idempotencia
sin acceder a Google.

La autorización de Calendar es incremental y está separada del login. El login
conserva `openid email profile`; Calendar solicita únicamente `openid` para
comprobar la cuenta vinculada y
`https://www.googleapis.com/auth/calendar.events.owned` para crear eventos en
el calendario principal del Cliente.

## Google Cloud

En el mismo proyecto y cliente OAuth web que ya usa FitPath:

1. Habilitar **Google Calendar API**.
2. En la pantalla de consentimiento, declarar el alcance sensible
   `https://www.googleapis.com/auth/calendar.events.owned`. Si la aplicación
   sigue en modo prueba, agregar como usuario de prueba la cuenta usada.
3. Agregar al cliente OAuth web esta URI de redirección autorizada exacta:

```text
http://localhost:5000/auth/google/calendar/callback
```

No hace falta agregar un origen JavaScript. En un despliegue, registrar la URI
HTTPS exacta del entorno.

## Variables locales

Se reutilizan `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`. Agregar al `.env`
ignorado por Git:

```dotenv
GOOGLE_CALENDAR_REDIRECT_URI=http://localhost:5000/auth/google/calendar/callback
GOOGLE_CALENDAR_TOKEN_SECRET=<secreto aleatorio exclusivo de al menos 32 caracteres>
```

Generar el secreto sin compartirlo ni versionarlo:

```powershell
& ".\.venv\Scripts\python.exe" -c "import secrets; print(secrets.token_urlsafe(48))"
```

Aplicar la migración y reiniciar Flask:

```powershell
& ".\.venv\Scripts\python.exe" -m backend.migrate --environment development
```

## Pasos para reproducir la validación real

Iniciar sesión como Cliente vinculado, abrir **Clases y reservas**, autorizar
Calendar y confirmar **Añadir a Google Calendar** sobre una inscripción activa.
Comprobar en Google Calendar actividad, sede, dirección, fecha, horario y zona
horaria. Repetir la acción debe informar que el evento ya existe, sin duplicarlo.
Los refresh tokens se cifran en SQLite y nunca se exponen al navegador.
