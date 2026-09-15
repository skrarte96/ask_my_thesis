# Evalúa que las secciones de donde está tomando la información son las correctas
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
K = 5


def ruta_contiene(ruta, esperada):
    for segmento in ruta.split(" > "):
        if segmento.strip().startswith(esperada):
            return True
    return False


def evaluar_una(caso, resultados):
    rutas = [r["seccion"] for r in resultados]
    esperadas = caso["secciones"]

    encontradas = [
        e for e in esperadas
        if any(ruta_contiene(ruta, e) for ruta in rutas)
    ]

    posicion = None
    for i, ruta in enumerate(rutas, 1):
        if any(ruta_contiene(ruta, e) for e in esperadas):
            posicion = i
            break

    return {
        "pregunta": caso["pregunta"],
        "tipo": caso["tipo"],
        "esperadas": esperadas,
        "encontradas": encontradas,
        "recuperadas": rutas,
        "similitud_max": resultados[0]["similitud"],
        "posicion": posicion,
    }


def resumir(evaluaciones):
    por_tipo = defaultdict(list)

    for e in evaluaciones:
        por_tipo[e["tipo"]].append(e)

    return por_tipo


if __name__ == "__main__":
    with open(PREGUNTAS, "r", encoding="utf-8") as f:
        casos = json.load(f)

    chunks, vectores = cargar_indice()
    modelo = cargar_modelo()

    print(f"\nEvaluando {len(casos)} preguntas con k={K}...\n")

    evaluaciones = []
    for caso in casos:
        resultados = buscar(modelo, chunks, vectores, caso["pregunta"], k=K)
        evaluaciones.append(evaluar_una(caso, resultados))

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(evaluaciones, f, ensure_ascii=False, indent=2)

    reales = [e for e in evaluaciones if e["esperadas"]]
    trampas = [e for e in evaluaciones if not e["esperadas"]]

    aciertos_alguna = sum(1 for e in reales if e["encontradas"])
    aciertos_todas = sum(
        1 for e in reales if len(e["encontradas"]) == len(e["esperadas"])
    )

    print(f"=== RECALL@{K} sobre {len(reales)} preguntas reales ===")
    print(f"Encuentra alguna sección esperada: {aciertos_alguna}/{len(reales)}"
          f"  ({aciertos_alguna / len(reales):.0%})")
    print(f"Encuentra todas las esperadas:     {aciertos_todas}/{len(reales)}"
          f"  ({aciertos_todas / len(reales):.0%})")

    posiciones = [e["posicion"] for e in reales if e["posicion"]]
    if posiciones:
        print(f"Posición media del primer acierto: {statistics.mean(posiciones):.1f}")

    print(f"\n=== POR TIPO ===")
    for tipo, grupo in sorted(resumir(reales).items()):
        n = sum(1 for e in grupo if e["encontradas"])
        print(f"{tipo:>12}: {n}/{len(grupo)}  ({n / len(grupo):.0%})")

    print(f"\n=== FALLOS ===")
    for e in reales:
        if not e["encontradas"]:
            print(f"\n[{e['tipo']}] {e['pregunta']}")
            print(f"   esperaba: {e['esperadas']}")
            for ruta in e["recuperadas"][:3]:
                print(f"   trajo:    {ruta[:85]}")

    sim_reales = [e["similitud_max"] for e in reales]
    sim_trampas = [e["similitud_max"] for e in trampas]

    print(f"\n=== SIMILITUD MÁXIMA ===")
    print(f"Preguntas reales:  media {statistics.mean(sim_reales):.3f}, "
          f"mínimo {min(sim_reales):.3f}")
    print(f"Preguntas trampa:  media {statistics.mean(sim_trampas):.3f}, "
          f"máximo {max(sim_trampas):.3f}")
    print(f"\nSeparación: {min(sim_reales) - max(sim_trampas):+.3f}")