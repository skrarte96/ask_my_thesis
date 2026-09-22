# De las evaluaciones que los scripts han hecho de las preguntas que hemos escrito específicas para la tesis
# ahora vemos cómo de bien han respondido a las preguntas los 4 modelos y evaluamos a mano las respuestas generadas
from pathlib import Path    # Rutas en Python
import json                 # Gestión de .json
import sys                  # Acceder a elementos del sistema (Nosotros, leer argumentos de la línea de comandos)
import textwrap             # Para repartir texto en estructura dada (tener un ancho fijo de respuestas)

# En caso de que el programa detecte caracteres que se le atraganten en vez de crashear, reemplaza dichos caracteres
# por un ?
sys.stdin.reconfigure(encoding="utf-8", errors="replace")

# Rutas a usar
RAIZ = Path(__file__).resolve().parent.parent               # Raíz del proyecto
DIR_EVAL = RAIZ / "data" / "processed" / "evaluaciones"     # Evaluaciones anteriores generadas
DIR_NOTAS = RAIZ / "data" / "notas"                         # Guardamos aquí nuestra impresión de respuestas generadas


ANCHO = 88  # Ancho de las líneas de respuesta (evitamos todo un párrafo en una línea y así sea legible)

# Evaluación de respuestas
ESCALA = {
    "s": "si",          # Responde la pregunta bien
    "p": "parcial",     # Todo lo que dice es correcto pero hay algún dato mal aplicado o incorrecto
    "n": "no",          # Contiene información falsa
}

# Preparamos cómo se va a ver el texto, separando los párrafos por su \n y aplicando la anchura indicada en ANCHO
def envolver(texto, sangria=""):
    lineas = []
    for parrafo in texto.split("\n"):
        if parrafo.strip():
            lineas.append(textwrap.fill(
                parrafo, width=ANCHO,
                initial_indent=sangria, subsequent_indent=sangria,
            ))
        else:
            lineas.append("")
    return "\n".join(lineas)

# Función para indicar que respondamos a la pregunta
def preguntar(etiqueta):
    # Opciones que se pueden resplnder
    opciones = "/".join(ESCALA)
    while True:
        # Metemos respuesta
        r = input(f"  {etiqueta} [{opciones}] > ").strip().lower()

        # Si respuesta dentro de las aceptables la guardamos
        if r in ESCALA:
            return ESCALA[r]
        # Si es x es que salimos de evaluar las preguntas
        if r == "x":
            return None

        # Si metemos tecla que no es nos redirige hasta que ponemos una de las respuestas aceptables
        print(f"  Responde {opciones}, o 'x' para salir y guardar.")


def mostrar(caso, mostrar_contexto):
    print("\n" + "=" * ANCHO)
    # Muestra número de la pregunta, tipo y tiempo que se tardó en responder a la pregunta
    print(f"[{caso['n']}/41]  tipo: {caso['tipo']}  "
          f"({caso['segundos']}s)")
    print("=" * ANCHO)
    # Llamamos a envolver para que muestre la pregunta que hemos hecho
    print(envolver(caso["pregunta"]))

    # Distinguimos si es pregunta trampa, si fuese trampa caso["secciones_esperadas"] = [] y es False
    if caso["secciones_esperadas"]:
        print(f"\nEsperado en: {', '.join(caso['secciones_esperadas'])}")
    else:
        print("\nPregunta trampa: debería abstenerse")
    # Llamamos a envolver para que muestre la respuesta generada
    print("\n--- RESPUESTA " + "-" * (ANCHO - 14))
    print(envolver(caso["respuesta"]))

    # Muestra los chunks que buscó para responder y los printea
    print("\n--- CONTEXTO RECUPERADO " + "-" * (ANCHO - 24))
    for c in caso["contexto"]:
        ultimo = c["seccion"].split(" > ")[-1]
        print(f"  {c['similitud']:.3f}  {ultimo[:70]}")

    if mostrar_contexto:
        for c in caso["contexto"]:
            print("\n" + envolver(c["seccion"], sangria="  "))
            print(envolver(c["texto"], sangria="    "))

    print()


if __name__ == "__main__":
    # Sacamos longitud de la lista de argumentos de la línea de comandos.
    # Si es menor que 2 es que no metimos ningún argumento. Te dice como usarlo y te muestra los modelos disponibles
    if len(sys.argv) < 2:
        # Busca los .json disponibles y saca los nombres de archivo sin la extensión
        disponibles = sorted(p.stem for p in DIR_EVAL.glob("*.json"))
        print("Uso: python -m src.puntuar <tanda> [--contexto]")
        print("\nTandas disponibles:")
        # Da los nombres de los archivos .json dismponibles
        for d in disponibles:
            print(f"  {d}")
        # Indicador de errores 0 (todo bien) cualquier otra cosa es error.
        raise SystemExit(1)


    tanda = sys.argv[1]                                 # Saca el nombre del modelo
    mostrar_contexto = "--contexto" in sys.argv         # True o False si hemos incluído --contexto en el comando o no

    entrada = DIR_EVAL / f"{tanda}.json"                # Sacamos ruta de las respuestas generadas para ese modelo
    if not entrada.exists():                            # En caso de no encontrar entrada
        raise SystemExit(f"No encuentro {entrada}")

    with open(entrada, "r", encoding="utf-8") as f:     # Cargamos las respuestas generadas
        datos = json.load(f)

    DIR_NOTAS.mkdir(parents=True, exist_ok=True)        # Creamos ruta de donde guardaremos las notas
    salida = DIR_NOTAS / f"{tanda}.json"

    if salida.exists():                                 # Di tenemos notas que poner las guarda en el archivo
        with open(salida, "r", encoding="utf-8") as f:
            notas = json.load(f)
    else:
        notas = {}                                      # Si no hay notas, crea un diccionario vacío

    casos = datos["resultados"]                                     # Saca las respuestas generadas
    pendientes = [c for c in casos if str(c["n"]) not in notas]     # Devuelve las respuestas pendientes
                                                                    # de evaluar por nosotros


    print(f"\nTanda: {tanda}")
    print(f"Puntuadas: {len(notas)}/{len(casos)}  "
          f"Pendientes: {len(pendientes)}")
    print("\nEn cada pregunta: s = sí, p = parcial, n = no, x = salir\n")

    for caso in pendientes:
        mostrar(caso, mostrar_contexto)             # Muestra la respuesta a la pregunta

        correcta = preguntar("¿Correcta?")          # Evaluamos la respuesta generada
        if correcta is None:
            break

        completa = preguntar("¿Completa?")          # Evaluamos cómo de completa está
        if completa is None:
            break

        comentario = input("  Comentario (Enter para saltar) > ").strip()   # Si queremos dejar un comentario

        # Apuntamos las notas que hemos dejado
        notas[str(caso["n"])] = {
            "correcta": correcta,
            "completa": completa,
            "comentario": comentario,
        }

        # Guardamos en notas la evaluación de esa pregunta
        with open(salida, "w", encoding="utf-8") as f:
            json.dump(notas, f, ensure_ascii=False, indent=2)

    print(f"\n\nGuardado: {len(notas)}/{len(casos)} puntuadas en {salida.name}")