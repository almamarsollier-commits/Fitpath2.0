# FitPath Smart Assistant

## Alcance verificado

Smart Assistant es un motor conversacional determinista escrito en JavaScript
Vanilla. No usa modelos descargables, servicios pagos, plugins ni conexión a
internet para responder consultas generales.

Sus módulos separan normalización de texto, coincidencia aproximada, detección
de intenciones, base de conocimientos, contexto reciente, acceso a FitPath e
interfaz visual. La base cubre entrenamiento, recuperación, nutrición general,
hidratación y hábitos saludables. No diagnostica, prescribe tratamientos ni
presenta orientación general como un plan clínico individual.

## Modos de ejecución

### Demostración portable sin Python

Abrir `demo/assistant/index.html` directamente con Edge, Chrome o Firefox. La
demostración usa scripts clásicos para funcionar bajo `file://` y evitar las
restricciones habituales de módulos ES locales.

En este modo funcionan el chat, las preguntas generales, el contexto, las
sugerencias y la navegación demostrativa. El estado indica `Modo offline` y
ninguna consulta o modificación real se presenta como completada.

### Integración con FitPath

Con Flask activo y una sesión Cliente válida, el widget de las vistas Cliente
consulta únicamente endpoints protegidos del mismo origen:

- clases futuras, horarios y cupos disponibles;
- última rutina propia;
- último registro de progreso propio;
- membresía activa propia.

La API exige sesión, rol `Cliente` y el permiso persistido
`cliente.datos.ver`. Las respuestas privadas usan `Cache-Control: private,
no-store` y nunca aceptan un identificador de cliente suministrado por el
frontend.

Las inscripciones y cancelaciones están deshabilitadas. Aunque existe un
servicio interno de alta, todavía no resuelve elegibilidad por membresía y no
existe un servicio de cancelación aprobado. No se agregaron endpoints que
pudieran omitir esas reglas. El asistente informa la limitación y no registra
reservas ficticias.

## Ejecución del proyecto completo

Desde la raíz del repositorio, en la computadora preparada:

```powershell
& ".\Fithpad2.0\.venv\Scripts\python.exe" -m backend.seed --environment development
$env:FLASK_APP = "backend.fitpath:create_app"
& ".\Fithpad2.0\.venv\Scripts\python.exe" -m flask run
```

Copiar la carpeta a una PC sin Python no permite ejecutar Flask ni SQLite a
través de la aplicación. Para la presentación inmediata debe usarse la
demostración estática. Un ejecutable autocontenido de todo FitPath requeriría
un bloque de empaquetado separado, una herramienta de compilación y pruebas en
una PC limpia; no se considera preparado ni verificado todavía.

## Verificación

- `python -m unittest discover -s tests -v`: 126 pruebas aprobadas.
- Prueba `file://` en Edge: 13 escenarios aprobados.
- La API tiene pruebas de sesión, rol, permiso, datos propios, cupos y ausencia
  de mutaciones no validadas.
