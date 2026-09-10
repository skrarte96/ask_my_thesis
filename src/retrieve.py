# Importamos las librerias para las rutas y la gestion de archivos .json
from pathlib import Path
import json

# Necesario para la vectorización de nuestros resultados
import numpy as np

# Cargamos funciones de nuestro propio script distinto para cargar nuestro modelo y vectorizar la pregunta del usuario
from src.embed import cargar_modelo, vectorizar_pregunta

# Raiz de nuestro proyecto, los chunks creados, los vectores creados que apuntan a cada chunk
RAIZ = Path(__file__).resolve().parent.parent
CHUNKS = RAIZ / "data" / "processed" / "chunks.json"
VECTORES = RAIZ / "data" / "processed" / "embeddings.npy"


TOP_K = 5       # El k = 5 es el estándar, son los chunks a recuperear.
UMBRAL = 0.80   # Para una similitud por debajo de este UMBRAL, no consideramos la respuesta como aceptable
# El umbral es alto porque nuestro modelo E5 tiende a darnos unas similitudes altas

# Cargamos tanto los chunks creados anteriormente como los vectores.
def cargar_indice():
    with open(CHUNKS, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    vectores = np.load(VECTORES)
    return chunks, vectores

# Nos devuelve los 5 mejores chunks que van a responder a nuestra pregunta.
def buscar(modelo, chunks, vectores, pregunta, k=TOP_K):
    # Vectorizamos la pregunta del usuario
    v_pregunta = vectorizar_pregunta(modelo, pregunta)

    # Calculamos las similitudes con el producto escalar entre nuestra matriz de chunks vectorizados la pregunta del usuario
    similitudes = vectores @ v_pregunta

    # Sacamos los índices de nuestro vector de similitudes creado, primero los ordenamos de mayor a menor similitud y luego
    # cogemos los top 5.
    mejores = np.argsort(similitudes)[::-1][:k]

    # Lista de diccionarios con las 5 mejores respuestas.
    resultados = []
    for i in mejores:
        resultados.append({
            "similitud": float(similitudes[i]),    # Similitud
            "seccion": chunks[i]["seccion"],        # Seccion a la que pertenece en la tesis
            "parte": chunks[i]["parte"],            # Chunk del que proviene
            "texto": chunks[i]["texto_limpio"],     # Texto limpio sin la ruta pegada
        })

    return resultados

# Solo carga si cargamos desde aquí directamente no si llamamos funciones específicas importadas de aquí a otro archivo
if __name__ == "__main__":
    # Sacamos los chunks y vectores a tratar
    chunks, vectores = cargar_indice()
    # Cargamos nuestro modelo
    modelo = cargar_modelo()

    # Indicaciín de que hemos cargado nuestro modelo
    print(f"\nÍndice cargado: {len(chunks)} chunks\n")
    print("Escribe una pregunta (o 'salir' o 'exit' o 'q' para terminar)\n")

    # Bucle infinito hasta que se declare un input
    while True:
        # Declaración de la pregunta por parte del usuario
        pregunta = input("> ").strip()

        # En caso de querer salir sin hacer la pregunta
        if pregunta.lower() in {"salir", "exit", "q"}:
            break

        # Si no hay ninguna pregunta(texto en blanco)
        if not pregunta:
            continue

        # Sacamos la función de resultados para que nos de los TOP_K mejores resultados
        resultados = buscar(modelo, chunks, vectores, pregunta)

        # Descripción de resultados
        print()
        for r in resultados:
            # Marca con un ! las respuestas que están por debajo de nuestro UMBRAL
            marca = " " if r["similitud"] >= UMBRAL else "!"
            print(f"{marca} {r['similitud']:.3f}  {r['seccion']} (parte {r['parte']})")
            print(f"     {r['texto'][:200]}...\n")