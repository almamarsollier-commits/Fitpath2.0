
from services.exercise_catalog import obtener_ejercicios

print("CONSULTANDO CATALOGO DE WGER...\n")

ejercicios = obtener_ejercicios(limite=5)

if ejercicios:
    print(f"Se encontraron {len(ejercicios)} ejercicios.\n")

    for ejercicio in ejercicios:
        print("Nombre:", ejercicio["nombre"])
        print("Categoría:", ejercicio["categoria"])
        print("Descripción:", ejercicio["descripcion"][:150])
        print("Imágenes:", ejercicio["imagenes"])
        print("--------------------------")
else:
    print("No se encontraron ejercicios.")
