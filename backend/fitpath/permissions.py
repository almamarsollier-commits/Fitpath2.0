"""Catálogo mínimo de permisos respaldados por funcionalidades existentes."""


CLIENT_VIEWS_PERMISSION = "cliente.vistas.ver"
CLIENT_DATA_PERMISSION = "cliente.datos.ver"
TRAINER_VIEWS_PERMISSION = "entrenador.vistas.ver"
TRAINER_DATA_PERMISSION = "entrenador.datos.gestionar"
MANAGER_VIEWS_PERMISSION = "jefe_sede.vistas.ver"
MANAGER_DATA_PERMISSION = "jefe_sede.datos.gestionar"
ADMIN_VIEWS_PERMISSION = "administrador.vistas.ver"
ADMIN_DATA_PERMISSION = "administrador.datos.gestionar"
TECHNICIAN_VIEWS_PERMISSION = "tecnico.vistas.ver"
TECHNICIAN_DATA_PERMISSION = "tecnico.mantenimiento.gestionar"

INITIAL_ROLE_PERMISSIONS = (
    (
        CLIENT_VIEWS_PERMISSION,
        "Acceder a las vistas protegidas del Cliente.",
        "Cliente",
    ),
    (
        CLIENT_DATA_PERMISSION,
        "Consultar datos propios del Cliente mediante la API.",
        "Cliente",
    ),
    (
        TRAINER_VIEWS_PERMISSION,
        "Acceder a las vistas protegidas del Entrenador.",
        "Entrenador",
    ),
    (
        TRAINER_DATA_PERMISSION,
        "Gestionar clases, rutinas y alumnos autorizados del Entrenador.",
        "Entrenador",
    ),
    (
        MANAGER_VIEWS_PERMISSION,
        "Acceder a las vistas protegidas del Jefe de sede.",
        "Jefe de sede",
    ),
    (
        MANAGER_DATA_PERMISSION,
        "Gestionar actividades, horarios y cupos de la sede asignada.",
        "Jefe de sede",
    ),
    (
        ADMIN_VIEWS_PERMISSION,
        "Acceder a las vistas protegidas del Administrador.",
        "Administrador",
    ),
    (
        ADMIN_DATA_PERMISSION,
        "Gestionar catálogos, usuarios, permisos y reportes administrativos.",
        "Administrador",
    ),
    (
        TECHNICIAN_VIEWS_PERMISSION,
        "Acceder a las vistas protegidas del Técnico de mantenimiento.",
        "Técnico de mantenimiento",
    ),
    (
        TECHNICIAN_DATA_PERMISSION,
        "Gestionar máquinas, tickets e historial de la sede asignada.",
        "Técnico de mantenimiento",
    ),
)
