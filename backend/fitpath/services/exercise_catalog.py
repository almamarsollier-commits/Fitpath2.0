import requests

WGER_API_URL = "https://wger.de/api/v2"


def normalizar_ejercicio(ejercicio):

    traducciones = ejercicio.get("translations", [])

    traduccion = next(
        (t for t in traducciones if t.get("language") == 4),
        None
    )

    if traduccion is None:
        traduccion = next(
            (t for t in traducciones if t.get("language") == 2),
            None
        )

    if traduccion is None and traducciones:
        traduccion = traducciones[0]

    if traduccion is None:
        traduccion = {}

    categoria = ejercicio.get("category") or {}

    return {
        "id": ejercicio.get("id"),
        "nombre": traduccion.get("name") or "Sin nombre",
        "descripcion": (
            traduccion.get("description")
            or traduccion.get("description_source")
            or ""
        ),
        "categoria": categoria.get("name", "Sin categoría"),
        "musculos": [
            musculo.get("name")
            for musculo in ejercicio.get("muscles", [])
        ],
        "equipamiento": [
            elemento.get("name")
            for elemento in ejercicio.get("equipment", [])
        ],
        "imagenes": [
            imagen.get("image")
            for imagen in ejercicio.get("images", [])
            if imagen.get("image")
        ],
        "videos": [
            video.get("video")
            for video in ejercicio.get("videos", [])
            if video.get("video")
        ]
    }


def obtener_ejercicios(limite=20):
    url = f"{WGER_API_URL}/exerciseinfo/"

    parametros = {
        "limit": limite,
        "language": 4
    }

    try:
        respuesta = requests.get(
            url,
            params=parametros,
            timeout=15
        )

        respuesta.raise_for_status()

        datos = respuesta.json()

        return [
            normalizar_ejercicio(ejercicio)
            for ejercicio in datos.get("results", [])
        ]

    except requests.RequestException as error:
        print(f"Error al consultar wger: {error}")
        return []


def obtener_ejercicio_por_id(ejercicio_id):
    url = f"{WGER_API_URL}/exerciseinfo/{ejercicio_id}/"

    try:
        respuesta = requests.get(url, timeout=15)
        respuesta.raise_for_status()

        ejercicio = respuesta.json()

        return normalizar_ejercicio(ejercicio)

    except requests.RequestException as error:
        print(f"Error al obtener ejercicio: {error}")
        return None
