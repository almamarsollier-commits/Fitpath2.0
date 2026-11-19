
import requests


WGER_API_URL = "https://wger.de/api/v2"


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

        ejercicios = []

        for ejercicio in datos.get("results", []):

            ejercicios.append({
                "id": ejercicio.get("id"),
                "nombre": ejercicio.get("name") or "Sin nombre",
                "descripcion": ejercicio.get("description") or "",
                "categoria": (
                    ejercicio.get("category", {}).get("name")
                    if ejercicio.get("category")
                    else "Sin categoría"
                ),
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
                ]
            })

        return ejercicios

    except requests.RequestException as error:
        print(f"Error al consultar wger: {error}")
        return []


def obtener_ejercicio_por_id(ejercicio_id):

    url = f"{WGER_API_URL}/exerciseinfo/{ejercicio_id}/"

    try:
        respuesta = requests.get(
            url,
            timeout=15
        )

        respuesta.raise_for_status()

        ejercicio = respuesta.json()

        return {
            "id": ejercicio.get("id"),
            "nombre": ejercicio.get("name") or "Sin nombre",
            "descripcion": ejercicio.get("description") or "",
            "categoria": (
                ejercicio.get("category", {}).get("name")
                if ejercicio.get("category")
                else "Sin categoría"
            ),
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
            ]
        }

    except requests.RequestException as error:
        print(f"Error al obtener ejercicio: {error}")
        return None
