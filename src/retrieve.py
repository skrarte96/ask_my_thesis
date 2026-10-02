# Sacamos los chunks más relevantes de la tesis para la pregunta realizada
# Importamos las librerias para las rutas y la gestion de archivos .json
from pathlib import Path
import json
import re
# Necesario para la vectorización de nuestros resultados
import numpy as np

# Cargamos funciones de nuestro propio script distinto para cargar nuestro modelo y vectorizar la pregunta del usuario
from src.embed import cargar_modelo, vectorizar_pregunta

# Raiz de nuestro proyecto, los chunks creados, los vectores creados que apuntan a cada chunk
RAIZ = Path(__file__).resolve().parent.parent
CHUNKS = RAIZ / "data" / "processed" / "chunks.json"
VECTORES = RAIZ / "data" / "processed" / "embeddings.npy"


TOP_K = 5       # El k = 5 es el estándar, son los chunks a recuperar.
UMBRAL = 0.80   # Para una similitud por debajo de este UMBRAL, no consideramos la respuesta como aceptable
# El umbral es alto porque nuestro modelo E5 tiende a darnos unas similitudes altas



# Preguntas de resumen: no se parecen a ningún fragmento concreto, así que la
# búsqueda vectorial nunca acierta con ellas. Las detectamos y traemos el Abstract.
RE_RESUMEN = re.compile(
    r"res[uú]me|resumen|de qu[eé] (va|trata)|sobre qu[eé] (va|trata)|"
    r"summar|overview|abstract|"
    r"what.{0,20}thesis.{0,20}about",
    re.IGNORECASE,
)

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
    mejores = list(np.argsort(similitudes)[::-1][:k])

    # El modelo se traba al buscar un resumen porque tiende a coger todos los chunks y resumir
    # Le ayudamos con este query routing
    # Si es una pregunta de resumen, el Abstract va primero sí o sí
    if RE_RESUMEN.search(pregunta):
        abstract = [i for i, c in enumerate(chunks) if c["ruta"][0] == "Abstract"]
        # Los del Abstract delante, y detrás los mejores que no estuvieran ya
        mejores = abstract + [i for i in mejores if i not in abstract]
        mejores = mejores[:k]

    # Lista de diccionarios con las 5 mejores respuestas.
    resultados = []
    for i in mejores:
        resultados.append({
            "similitud": float(similitudes[i]),     # Similitud
            "seccion": chunks[i]["seccion"],        # Sección a la que pertenece en la tesis
            "parte": chunks[i]["parte"],            # Chunk del que proviene
            "texto": chunks[i]["texto_limpio"],     # Texto limpio sin la ruta pegada
            "imagenes": chunks[i].get("imagenes", [])
        })

    return resultados

# Solo carga si cargamos desde aquí directamente no si llamamos funciones específicas importadas de aquí a otro archivo
if __name__ == "__main__":
    # Sacamos los chunks y vectores a tratar
    chunks, vectores = cargar_indice()
    # Cargamos nuestro modelo
    modelo = cargar_modelo()

    # Indicación de que hemos cargado nuestro modelo
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