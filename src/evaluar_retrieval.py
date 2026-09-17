# Evalúa que las secciones de donde está tomando la información son las correctas
# Comprueba si los chunks recuperados por nuestro programa se corresponden con los que hemos indicado a mano
# Da igual que el modelo de lenguaje sea el más potente si nuestro retrieval no le da los chunks que hacen falta
from pathlib import Path
from collections import defaultdict     # Crea entradas de diccionario cuando estas no existen y así no da error
import json                             # Gestion de los archivos .json
import statistics                       # Calculos estadísticos

# Nuestras funciones
from src.embed import cargar_modelo             # Llamamos a nuestro modelo
from src.retrieve import cargar_indice, buscar  # Cargamos tesis y buscamos los mejores chunks

# Los path de siempre con la raiz del proyecto, las preguntas que hemos escrito a mano y la ruta de salida que
# contiene la evaluación de las preguntas
RAIZ = Path(__file__).resolve().parent.parent
PREGUNTAS = RAIZ / "data" / "preguntas.json"
SALIDA = RAIZ / "data" / "processed" / "eval_retrieval.json"

# número de chunks de los que saca información
K_list = [3,5,10]

# Con esta funcion decidimos si un chunk recuperado corresponde a una sección recuperada
def ruta_contiene(ruta, esperada):
    # Vamos a la ruta y la dividimos por su título, sección y subsección y comprobamos las tres (si las hay)
    for segmento in ruta.split(" > "):
        # Vemos si empiezan igual el segmento con la ruta esperada de nuestro .json de preguntas
        if segmento.strip().startswith(esperada):
            return True
    # En caso de que en la ruta, los elementos no concuerden con la esperada es un False porque no hubo coincidencia
    return False


def evaluar_una(caso, resultados):
    # Saca las rutas de los chunks devueltos
    rutas = [r["seccion"] for r in resultados]
    # Las secciones escritas donde está la respuesta de nuestro .json
    esperadas = caso["secciones"]
    # Sacamos el texto de cada chunk recuperado
    textos = [r["texto"] for r in resultados]
    # En caso de que existan, conseguimos los datos de contiene
    contiene = caso.get("contiene")

    # Recorremos cada sección del .json y luego la comparamos con cada una de las rutas que devuelven los chunks.
    # En encontradas se devuelven aquellas rutas que coincidan con la sección puesta en el .json
    encontradas = [
        e for e in esperadas
        if any(ruta_contiene(ruta, e) for ruta in rutas)
    ]

    # Nos da la posición del chunk que presenta el primer acierto, es decir que chunk (previamente ordenado por
    # similitud de mayor a menor) nos dice cuál ha acertado con la sección que hemos puesto, si es el primero perfecto
    # si es de los últimos, no podemos bajar el valor de k porque el contexto bueno está en los últimos chunks
    # recuperados
    posicion = None
    # Recorremos las rutas por orden
    for i, ruta in enumerate(rutas, 1):
        # En cuanto una ruta acierta con la sección, esa es nuestra posición acertada
        if any(ruta_contiene(ruta, e) for e in esperadas):
            posicion = i
            break

    # None: no hay contiene.
    # True, la info está en los chunks recuperados.
    # False, la info no está en los chunks recuperados
    dato_presente = None
    if contiene:
        dato_presente = any(contiene in t for t in textos)

    # Devolvemos un diccionario con
    return {
        "pregunta": caso["pregunta"],                   # La pregunta escrita en el .json
        "tipo": caso["tipo"],                           # Tipo puesto en el .json
        "esperadas": esperadas,                         # Las secciones esperadas
        "encontradas": encontradas,                     # Las rutas que concuerdan con esas secciones
        "recuperadas": rutas,                           # Las rutas de todos los chunks recuperados
        "similitud_max": resultados[0]["similitud"],    # La máxima similitud que tiene el primer chunk
        "contiene": contiene,                           # En caso de que exista, lo que debe contener
        "dato_presente": dato_presente,                 # Contiene el dato? True o False
        "posicion": posicion,                           # Posición del chunk entre los k chunk que acertó con la/s
                                                        # secciones del .json que pusimos
    }

# Ordenamos las evaluaciones por tipo de pregunta del .json (general, comparativa, factual...)
def resumir(evaluaciones):
    # Creamos diccionario que no se rompe si no está la llave a la que guardamos valor sino que la crea y la guarda
    por_tipo = defaultdict(list)

    # Vamos guardando todas las evaluaciones
    for e in evaluaciones:
        por_tipo[e["tipo"]].append(e)

    # Devuelve el diccionario de evaluaciones ordenado por tipos
    return por_tipo


if __name__ == "__main__":
    # Abrimos y cargamos el .json de preguntas en casos
    with open(PREGUNTAS, "r", encoding="utf-8") as f:
        casos = json.load(f)

    # Cargamos la tesis en chunks y los vectores que apuntan a los chunks
    chunks, vectores = cargar_indice()
    # Cargamos el modelo
    modelo = cargar_modelo()

    for K in K_list:

        # Algo de info que se vea que está cargando
        print(f"\nEvaluando {len(casos)} preguntas con k={K}...\n")

        # Guardamos la info de evaluar_una(). Las evaluaciones a cada pregunta con los chunks que son de la seccion
        # apropiada y los que no
        evaluaciones = []
        for caso in casos:
            # Los chunks con mayor similitud que nos da el programa
            resultados = buscar(modelo, chunks, vectores, caso["pregunta"], k=K)
            # Guardamos las evaluaciones
            evaluaciones.append(evaluar_una(caso, resultados))

        # Creamos un .json con la salida de las evaluaciones de las preguntas
        with open(SALIDA, "w", encoding="utf-8") as f:
            json.dump(evaluaciones, f, ensure_ascii=False, indent=2)

        # Aquí van las evaluaciones de verdad, sin las trampas (que no tienen sección correcta)
        reales = [e for e in evaluaciones if e["esperadas"]]
        # Aquí van las trampas
        trampas = [e for e in evaluaciones if not e["esperadas"]]

        # Sumamos todas las evaluaciones que hayan acertado al menos una de las secciones del .json de preguntas
        aciertos_alguna = sum(1 for e in reales if e["encontradas"])
        # Sumamos las evaluaciones que acierten todas las secciones que eran necesarias del .json de preguntas (comparativa)
        aciertos_todas = sum(
            1 for e in reales if len(e["encontradas"]) == len(e["esperadas"])
        )

        # Info de los chunks que acertaron con la sección que tocaba en proporción y %
        print(f"=== RECALL@{K} sobre {len(reales)} preguntas reales ===")
        print(f"Encuentra alguna sección esperada: {aciertos_alguna}/{len(reales)}"
              f"  ({aciertos_alguna / len(reales):.0%})")
        print(f"Encuentra todas las esperadas:     {aciertos_todas}/{len(reales)}"
              f"  ({aciertos_todas / len(reales):.0%})")

        # Las posiciones del primer chunk que acertó para cada pregunta de entre los k chunks retrieved
        posiciones = [e["posicion"] for e in reales if e["posicion"]]
        # Si tenemos posiciones, la media de las mismas (queremos que se acerque lo máximo posible a 1)
        if posiciones:
            print(f"Posición media del primer acierto: {statistics.mean(posiciones):.1f}")

        # Ordena las evaluaciones y me saca el tipo y la evaluación y vamos uno a uno por esos pares
        print(f"\n=== POR TIPO ===")
        for tipo, grupo in sorted(resumir(reales).items()):
            # Devuelve el ratio y % de evaluaciones acertadas por tipo de pregunta
            n = sum(1 for e in grupo if e["encontradas"])
            print(f"{tipo:>12}: {n}/{len(grupo)}  ({n / len(grupo):.0%})")

        # Devuelve las evaluaciones que no encontraron ninguna de las secciones del .json
        print(f"\n=== FALLOS ===")
        for e in reales:
            if not e["encontradas"]:
                print(f"\n[{e['tipo']}] {e['pregunta']}")
                print(f"   esperaba: {e['esperadas']}")
                for ruta in e["recuperadas"][:3]:
                    ultimo = ruta.split(" > ")[-1]
                    print(f"   trajo:    {ultimo[:70]}")

        # Similitudes máximas entre las preguntas reales y las que son trampas
        # Calcular si podemos poner un umbral para separarlas o se tiene que encargar el LLM
        sim_reales = [e["similitud_max"] for e in reales]
        sim_trampas = [e["similitud_max"] for e in trampas]

        # Sacamos las evaluaciones que tienen relleno contiene
        con_dato = [e for e in reales if e["contiene"]]

        # En caso de que tengan dato
        if con_dato:
            # Sumamos las preguntas que sacaron el dato que hacía falta de los chunks
            presentes = sum(1 for e in con_dato if e["dato_presente"])

            # Info de los datos que ha encontrado
            print(f"\n=== RECALL ESTRICTO ({len(con_dato)} preguntas con dato) ===")
            print(f"El dato concreto llega al contexto: {presentes}/{len(con_dato)}"
                  f"  ({presentes / len(con_dato):.0%})")

            # Aquellos en los que encuentra la sección correcta pero no el dato que hace falta.
            falsos_aciertos = [
                e for e in con_dato
                if e["encontradas"] and not e["dato_presente"]
            ]

            # Info de los falsos aciertos en la consola
            if falsos_aciertos:
                print(f"\nFalsos aciertos ({len(falsos_aciertos)}): "
                      f"sección correcta pero sin el dato")
                for e in falsos_aciertos:
                    print(f"   {e['pregunta'][:65]}")
                    print(f"      buscaba: '{e['contiene']}'")

        # Info de las similitudes máximas
        print(f"\n=== SIMILITUD MÁXIMA ===")
        print(f"Preguntas reales:  media {statistics.mean(sim_reales):.3f}, "
              f"mínimo {min(sim_reales):.3f}")
        print(f"Preguntas trampa:  media {statistics.mean(sim_trampas):.3f}, "
              f"máximo {max(sim_trampas):.3f}")
        print(f"\nSeparación: {min(sim_reales) - max(sim_trampas):+.3f}")