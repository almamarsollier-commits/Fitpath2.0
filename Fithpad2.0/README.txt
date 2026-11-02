FITHPAD 2.0 — Base web inicial

ESTRUCTURA
Fithpad2.0/
├── README.txt
├── templates/
│   ├── index.html
│   ├── inicio.html
│   ├── buscador.html
│   └── perfil.html
└── statics/
    ├── css/
    │   └── fitpath.css
    └── js/
        └── fitpath.js

CÓMO ABRIR
1. Descomprimí la carpeta Fithpad2.0 completa.
2. Entrá en templates y abrí index.html con Chrome.
3. Registrate con un nombre, correo y contraseña de prueba.
4. Iniciá sesión. Podés recorrer Inicio, Actividades y Mi perfil desde el menú lateral.

IMPORTANTE
- Esta es una base frontend funcional para empezar el proyecto. El registro, el inicio de sesión y los datos de perfil se guardan en localStorage del navegador de ese dispositivo.
- Todavía no hay servidor ni base de datos. No uses contraseñas reales ni información sensible: localStorage no es un sistema de autenticación seguro.
- Las rutas entre HTML, CSS y JavaScript están preparadas para esta estructura exacta. Mantené templates y statics al mismo nivel.
- Para una aplicación multiusuario real, más adelante hay que conectar el frontend con un backend y una base de datos.
