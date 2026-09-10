# Librería de los path y para gestionar archivos .json
from pathlib import Path
import json
# La usaremos para descargar el modelo a usar, tokenizar el texto, pasar por la red neuronal y devolver el vector
from sentence_transformers import SentenceTransformer
# Importamos numpy para las vectorizaciones
import numpy as np

# Los path de la raiz del proyecto, la entrada con el texto útil de la tesis ya en chunks y la salida donde irán nuestros
# embeddings
RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "data" / "processed" / "chunks.json"
SALIDA = RAIZ / "data" / "processed" / "embeddings.npy"

# Modelo de Hugging Face que usaremos. Lo hemos elegido frente a los otros encontrados porque nos ofrece un modelo
# multilingue con 768 dimensiones, algo altas pero con un buen ordenador corre bien en local
MODELO = "intfloat/multilingual-e5-base"

# Función para cargar el modelo. Podríamos trabajar con menos funciones pero me parece más limpio así.
def cargar_modelo(nombre=MODELO):
    # Pequeño print para indicar que, como la primera vez tarda bastante, el programa no se ha colgado
    print(f"Cargando modelo {nombre}...")
    return SentenceTransformer(nombre)

# Vectorizamos nuestros chunks, incluyendo el passage: que requiere el modelo multilingual-e5-base
# para trabajar con ellos
def vectorizar_chunks(modelo, chunks):
    textos = [f"passage: {c['texto']}" for c in chunks]

    # Codificamos los vectores en batches de 16, enseñando la barra de progreso y normalizando nuestros vectores en magnitud
    vectores = modelo.encode(
        textos,
        batch_size=16,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    return vectores

# Vectorizamos la pregunta. Lo usaremos en otro script pero ya incluimos toda la estructura de preguntas y respuestas aquí.
# Incluimos query: a nuestra pregunta por necesidades del modelo multilingual-e5-base
def vectorizar_pregunta(modelo, pregunta):
    return modelo.encode(
        f"query: {pregunta}",
        normalize_embeddings=True,
    )

# Para que cargue solo si corremos desde aquí
if __name__ == "__main__":

    # Cargamos nuestro archivo de secciones.json
    with open(ENTRADA, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    # Cargamos nuestro modelo y vectorizamos los chunks
    modelo = cargar_modelo()
    vectores = vectorizar_chunks(modelo, chunks)

    # Guardamos en nuestra ruta de salidas nuestros vectores generados
    np.save(SALIDA, vectores)

    # Checkear que nuestro numpy array tiene las dimensiones que queremos y que se ha guardado en la ruta deseada
    print(f"\nVectores generados: {vectores.shape[0]}")
    print(f"Dimensiones por vector: {vectores.shape[1]}")
    print(f"Guardado en: {SALIDA}")