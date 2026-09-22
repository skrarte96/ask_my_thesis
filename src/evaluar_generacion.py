# Pasa las preguntas que hemos escrito a mano por dos modelos de ollama con 2 k (chunks retrieved) distintas
# (5 y 10) y devuelve las evaluaciones de los modelos con su respuesta
from pathlib import Path    # Rutas de Python
import json                 # Gestion de .json
import time                 # Para medir cuánto tarda cada respuesta

from tqdm import tqdm       # Crear barras de progreso

from src.embed import cargar_modelo                     # Carga del modelo
from src.retrieve import cargar_indice, buscar          # Cargamos la tesis y buscamos chunk
from src.generate import generar_respuesta, SISTEMA     # Generamos respuesta y usamos prompt de comportamiento

# Rutas a los archivos
RAIZ = Path(__file__).resolve().parent.parent               # Ruta raíz del proyecto
PREGUNTAS = RAIZ / "data" / "preguntas.json"                # Para las preguntas escritas
DIR_SALIDA = RAIZ / "data" / "processed" / "evaluaciones"   # Donde guardaremos las evaluaciones

# Las configuraciones de modelos y k chunks recuperados por pregunta a probar
CONFIGURACIONES = [
    {"modelo": "qwen2.5:14b", "k": 5},
]

# Frase en caso de que la pregunta no tenga que ver con la tesis
FRASES_ABSTENCION = (
    "Esa información no aparece en la tesis",
    "That information does not appear in the thesis",
)
# Función de abstención de respuesta
def se_abstiene(respuesta):
    return any(f in respuesta for f in FRASES_ABSTENCION)

# Muestra el progreso de las preguntas que van contestando los modelos y crea las evaluaciones generadas por los
# modelos.
def generar_tanda(casos, chunks, vectores, modelo_emb, config):
    resultados = []
    fallos = 0
    # Barra de progreso para que se vea el progreso de los modelos según vayan contestando las preguntas
    # Muestra el modelo, el k, la barra (% de preguntas contstadas) cambiamos unidad a preg (de pregunta)
    # eso es tiempo medio por pregunta. Casos representa todas las preguntas
    barra = tqdm(casos, desc=f"{config['modelo']} k={config['k']}", unit="preg")

    # para cada pregunta en la barra, previamente enumeradas dichas preguntas
    for i, caso in enumerate(barra, 1):
        # Sacamos los chunks
        recuperados = buscar(
            modelo_emb, chunks, vectores, caso["pregunta"], k=config["k"]
        )
        # Contamos desde aquí porque queremos el tiempo de generación de respuesta no el de sacar los chunks
        inicio = time.time()
        # Probamos a generar respuesta
        try:
            respuesta = generar_respuesta(
                caso["pregunta"], recuperados, modelo=config["modelo"]
            )
            error = None
        # En caso de error de generación, apuntamos el fallo
        except Exception as e:
            respuesta = ""
            error = str(e)
            fallos += 1
        # Sacamos los segundos que se tardó en generar la respuesta
        segundos = time.time() - inicio

        # Incluimos los fallos que se han obtenido y los segundos que tardó la última generación
        barra.set_postfix(fallos=fallos, ultimo=f"{segundos:.0f}s")

        # Adjuntamos la evaluación
        resultados.append({
            "n": i,                                         # Número de pregunta
            "pregunta": caso["pregunta"],                   # La pregunta
            "tipo": caso["tipo"],                           # Tipo de pregunta (en el .json)
            "secciones_esperadas": caso["secciones"],       # Secciones esperadas (en el .json)
            "respuesta": respuesta,                         # Respuesta generada por el modelo
            "error": error,                                 # Si hubo error
            "segundos": round(segundos, 1),                 # Segundos que se tardó en responder
            "contexto": [
                {
                    "similitud": round(r["similitud"], 3),  # Similitud con entre pregunta y chunks retrieved
                    "seccion": r["seccion"],                # Secciones encontradas en los chunks recuperados
                    "texto": r["texto"],                    # Texto de los chunks
                }
                for r in recuperados
            ],
        })

    # Cerramos la barra de progreso que ya cumplió su función
    barra.close()

    # Guardamos los segundos que tardó la generación de respuesta para las respuestas que no dieron error
    tiempos = [r["segundos"] for r in resultados if not r["error"]]
    # Si hubo respuestas sin error, calculamos el tiempo medio
    if tiempos:
        print(f"  Tiempo medio por respuesta: {sum(tiempos) / len(tiempos):.1f}s")

    return resultados


def resumir_tanda(resultados):
    # Preguntas trampa
    trampas = [r for r in resultados if r["tipo"] == "trampa"]
    # Preguntas de verdad
    reales = [r for r in resultados if r["tipo"] != "trampa"]

    # Número de preguntas trampa seleccionadas
    aciertos_trampa = sum(
        1 for r in trampas if se_abstiene(r["respuesta"])
    )
    # Número de preguntas reales que se clasificaron como trampa
    falsas = sum(
        1 for r in reales if se_abstiene(r["respuesta"])
    )
    # Número de respuestas que generaron error
    errores = sum(1 for r in resultados if r["error"])


    return {
        "abstenciones_correctas": aciertos_trampa,  # Las veces que acertó que era una pregunta trampa
        "total_trampas": len(trampas),              # Total de número de preguntas trampa
        "abstenciones_indebidas": falsas,           # Preguntas clasificadas como trampa pero que eran reales
        "total_reales": len(reales),                # Total de preguntas reales
        "errores": errores,                         # Errores cometidos por la generación de respuestas
    }


if __name__ == "__main__":
    # Cargamos nuestras preguntas
    with open(PREGUNTAS, "r", encoding="utf-8") as f:
        casos = json.load(f)

    chunks, vectores = cargar_indice()  # Cargamos la tesis en chunks y sus vectores
    modelo_emb = cargar_modelo()        # Cargamos el modelo a usar

    DIR_SALIDA.mkdir(parents=True, exist_ok=True)   # Creamos path con la salida de las evaluaciones

    resumenes = []

    # Lista con las combinaciones entre modelos usados y valores de k para dejar las evaluaciones de cada configuración
    # en un archivo distinto
    for config in CONFIGURACIONES:
        nombre = f"{config['modelo'].replace(':', '-')}_k{config['k']}"
        salida = DIR_SALIDA / f"{nombre}.json"

        print(f"\n=== {config['modelo']}  k={config['k']} ===")

        # Generamos las respuestas del modelo
        resultados = generar_tanda(casos, chunks, vectores, modelo_emb, config)

        # Guardamos las respuestas generadas, es decir, las evaluaciones
        with open(salida, "w", encoding="utf-8") as f:
            json.dump({
                "configuracion": config,
                "sistema": SISTEMA,
                "resultados": resultados,
            }, f, ensure_ascii=False, indent=2)

        # Para la info desplegada
        resumen = resumir_tanda(resultados)
        resumen["nombre"] = nombre
        resumenes.append(resumen)

        print(f"  Abstenciones correctas: "
              f"{resumen['abstenciones_correctas']}/{resumen['total_trampas']}")
        print(f"  Abstenciones indebidas: "
              f"{resumen['abstenciones_indebidas']}/{resumen['total_reales']}")
        if resumen["errores"]:
            print(f"  Errores: {resumen['errores']}")
        print(f"  Guardado en: {salida.name}")

    print(f"\n\n=== RESUMEN DE LAS {len(resumenes)} TANDAS ===\n")
    print(f"{'configuración':<22} {'abst. ok':>9} {'abst. mal':>10} {'errores':>8}")
    for r in resumenes:
        print(f"{r['nombre']:<22} "
              f"{r['abstenciones_correctas']:>4}/{r['total_trampas']:<4} "
              f"{r['abstenciones_indebidas']:>5}/{r['total_reales']:<4} "
              f"{r['errores']:>8}")