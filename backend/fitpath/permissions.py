"""Catálogo mínimo de permisos respaldados por funcionalidades existentes."""


CLIENT_VIEWS_PERMISSION = "cliente.vistas.ver"
CLIENT_DATA_PERMISSION = "cliente.datos.ver"

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
)
