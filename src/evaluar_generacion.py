from pathlib import Path
import json
import time

from tqdm import tqdm

from src.embed import cargar_modelo
from src.retrieve import cargar_indice, buscar
from src.generate import generar_respuesta, SISTEMA

RAIZ = Path(__file__).resolve().parent.parent
PREGUNTAS = RAIZ / "data" / "preguntas.json"
DIR_SALIDA = RAIZ / "data" / "processed" / "evaluaciones"

CONFIGURACIONES = [
    {"modelo": "qwen2.5:7b", "k": 5},
    {"modelo": "qwen2.5:7b", "k": 10},
    {"modelo": "qwen2.5:14b", "k": 5},
    {"modelo": "qwen2.5:14b", "k": 10},
]

FRASE_ABSTENCION = "Esa información no aparece en la tesis"


def generar_tanda(casos, chunks, vectores, modelo_emb, config):
    resultados = []
    fallos = 0

    barra = tqdm(casos, desc=f"{config['modelo']} k={config['k']}", unit="preg")

    for i, caso in enumerate(barra, 1):
        recuperados = buscar(
            modelo_emb, chunks, vectores, caso["pregunta"], k=config["k"]
        )

        inicio = time.time()
        try:
            respuesta = generar_respuesta(
                caso["pregunta"], recuperados, modelo=config["modelo"]
            )
            error = None
        except Exception as e:
            respuesta = ""
            error = str(e)
            fallos += 1
        segundos = time.time() - inicio

        barra.set_postfix(fallos=fallos, ultimo=f"{segundos:.0f}s")

        resultados.append({
            "n": i,
            "pregunta": caso["pregunta"],
            "tipo": caso["tipo"],
            "secciones_esperadas": caso["secciones"],
            "respuesta": respuesta,
            "error": error,
            "segundos": round(segundos, 1),
            "contexto": [
                {
                    "similitud": round(r["similitud"], 3),
                    "seccion": r["seccion"],
                    "texto": r["texto"],
                }
                for r in recuperados
            ],
        })

    barra.close()

    tiempos = [r["segundos"] for r in resultados if not r["error"]]
    if tiempos:
        print(f"  Tiempo medio por respuesta: {sum(tiempos) / len(tiempos):.1f}s")

    return resultados


def resumir_tanda(resultados):
    trampas = [r for r in resultados if r["tipo"] == "trampa"]
    reales = [r for r in resultados if r["tipo"] != "trampa"]

    aciertos_trampa = sum(
        1 for r in trampas if FRASE_ABSTENCION in r["respuesta"]
    )
    falsas = sum(
        1 for r in reales if FRASE_ABSTENCION in r["respuesta"]
    )
    errores = sum(1 for r in resultados if r["error"])

    return {
        "abstenciones_correctas": aciertos_trampa,
        "total_trampas": len(trampas),
        "abstenciones_indebidas": falsas,
        "total_reales": len(reales),
        "errores": errores,
    }


if __name__ == "__main__":
    with open(PREGUNTAS, "r", encoding="utf-8") as f:
        casos = json.load(f)

    chunks, vectores = cargar_indice()
    modelo_emb = cargar_modelo()

    DIR_SALIDA.mkdir(parents=True, exist_ok=True)

    resumenes = []

    for config in CONFIGURACIONES:
        nombre = f"{config['modelo'].replace(':', '-')}_k{config['k']}"
        salida = DIR_SALIDA / f"{nombre}.json"

        print(f"\n=== {config['modelo']}  k={config['k']} ===")

        resultados = generar_tanda(casos, chunks, vectores, modelo_emb, config)

        with open(salida, "w", encoding="utf-8") as f:
            json.dump({
                "configuracion": config,
                "sistema": SISTEMA,
                "resultados": resultados,
            }, f, ensure_ascii=False, indent=2)

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