# Esta será la capa de abstracción que gobierna entre backends y el prompt que gobierna cómo responde.
from pathlib import Path    # Rutas de Python
import json                 # Cargar y gestionar archivos .json
import textwrap             # Estructura de printeo de texto más human-friendly
# Hacer peticiones HTTP
import urllib.error         # Capturar fallos de red
import urllib.request       # Gestionar las peticiones


# Ruta Raiz del proyecto
RAIZ = Path(__file__).resolve().parent.parent

# URL de nuestro modelo descargado y el tipo de modelo
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODELO = "qwen2.5:7b"

# Nuestro tiempo que damos para que el modelo responda
TIMEOUT = 180

# El prompt del sistema.
SISTEMA = """Respondes preguntas sobre una tesis doctoral de física a partir de \
fragmentos que se te proporcionan.

PRIMERO decide: ¿los fragmentos contienen la respuesta?

Si NO la contienen, responde solo esta frase y nada más:
"Esa información no aparece en la tesis."

Si SÍ la contienen, sigue estas reglas:

IDIOMA: responde en el mismo idioma de la pregunta. Pregunta en inglés, \
respuesta en inglés.

SIGLAS: escribe STM, LDOS, DOS, BPEA, HOMO, LUMO tal cual, en su forma original. \
Nunca inventes qué significan.

DATOS: cada número, unidad y fórmula debe aparecer literalmente en los fragmentos, \
referido a la misma magnitud. No reutilices un dato para algo distinto de aquello \
a lo que se refiere.

CITAS: al final de cada frase, entre corchetes, el número de la subsección. \
Ejemplo: "...decae exponencialmente con la distancia [2.3.3]." Si varios \
fragmentos son de la misma subsección, cítala UNA sola vez. Nunca cites \
títulos ni texto, solo números.

FORMA: prosa continua, sin títulos ni encabezados. Conserva el LaTeX tal cual.

Antes de terminar, revisa que cada dato numérico de tu respuesta está en los \
fragmentos y se refiere a lo mismo."""

# Tenemos que meterle el contexto y la pregunta. Luego los incorporamos con format
PLANTILLA = """Contexto extraído de la tesis:

{contexto}

---

Pregunta: {pregunta}"""

# Convertimos los 5 chunks en un solo texto cada uno empezando por su ruta para poderlo citar y separados los 5 chunks
# por dobles líneas en blanco con --- entre medias de forma que se entienda que son 5 ideas distintas.
def formatear_contexto(resultados):
    bloques = []

    for r in resultados:
        bloques.append(f"[{r['seccion']}]\n{r['texto']}")

    return "\n\n---\n\n".join(bloques)

# Llamamos a Ollama creando la estructura .json que recibirá para la petición más Error Handling sobre el tiempo de
# respuesta de la petición. Si se pasa del tiempo TIMEOUT deja error de que no ha podido hablar con Ollama y pregunta si
# hemos corrido Ollama serve
def llamar_ollama(mensajes, modelo=OLLAMA_MODELO, url=OLLAMA_URL):
    # Cuerpo de la petición a Ollama
    cuerpo = {
        "model": modelo,                  # Indicamos el modelo
        "messages": mensajes,             # Lista de mensajes que incluirán el prompt del sistema y la plantilla rellena
        "stream": False,                  # Que salgan todos los token de golpe, en vez de poco a poco
        "options": {"temperature": 0.2},  # 0 respuesta rígida, 1 respuesta muy creativa y puede divagar
    }

    # Convertimos el cuerpo en lista de formato .json y luego codificamos a bytes
    datos = json.dumps(cuerpo).encode("utf-8")

    # Construimos la petición HTTP
    peticion = urllib.request.Request(
        url,                                            # Url a donde conectar
        data=datos,                                     # El json con el cuerpo codificado
        headers={"Content-Type": "application/json"},   # Indicamos al servidor que mandamos .json para descodificarlo
        method="POST",                                  # Porque enviamos datos
    )

    # Error Handling con el envío de la petición
    try:
        # Enviamos la petición
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:
            # Es el mensaje enviado vuelto a pasar de bytes a diccionario de Python
            resultado = json.loads(respuesta.read().decode("utf-8"))
    # En caso de que haya justo el tipo de error de conexión
    except urllib.error.URLError as e:
        # No hemos podido conectar con la URL y el error más probable será no haber conectado con Ollama (ollama serve)
        raise RuntimeError(
            f"No he podido hablar con Ollama en {url}. "
            f"¿Está corriendo 'ollama serve'? Detalle: {e}"
        )

    # Del texto generado solo nos interesa el mensaje y el contenido
    return resultado["message"]["content"]

# Es la capa de abstracción donde luego incorporaremos el resto de modelos que este proyecto aceptará
# De momento solo le guardamos la función de llamar a ollama como variable
BACKENDS = {
    "ollama": llamar_ollama,
}


def generar_respuesta(pregunta, resultados, backend="ollama", modelo = None):
    # Primero que nada chequeamos si el backend a meter es el correcto (tenemos un modelo aceptado de los que carga)
    if backend not in BACKENDS:
        raise ValueError(
            f"Backend '{backend}' desconocido. Disponibles: {list(BACKENDS)}"
        )

    # Con los resultados obtenidos de antes (los 5 chunks generados en retrieve.py con la función buscar, formateamos
    # los 5 chunks para crear el contexto
    contexto = formatear_contexto(resultados)

    # Creamos la lista de mensajes a enviar al modelo, en este caso el prompt principal de comportamiento y luego la
    # plantilla con el contexto recogido y la pregunta del usuario
    mensajes = [
        {"role": "system", "content": SISTEMA},         # Da más importancia al ser role = system (aquí comportamiento)
        {"role": "user", "content": PLANTILLA.format(
            contexto=contexto, pregunta=pregunta
        )},                                             # Contexto dado y pregunta del usuario
    ]

    # Sacamos la función de BACKENDS (el modelo a llamar) y luego los mensajes con el prompt, contexto y pregunta
    if modelo:
        return BACKENDS[backend](mensajes, modelo=modelo)
    return BACKENDS[backend](mensajes)

if __name__ == "__main__":
    # Cargamos nuestras funciones personales
    from src.embed import cargar_modelo
    from src.retrieve import cargar_indice, buscar

    # Generamos los chunks y sus vectores de toda la tesis
    chunks, vectores = cargar_indice()

    # Cargamos el modelo elegido
    modelo = cargar_modelo()

    # Mostramos el número de chunks e indicamos que se puede escribir la pregunta ya
    print(f"\nÍndice cargado: {len(chunks)} chunks")
    print("Escribe tu pregunta (para salir escribe 'salir', o 'exit', o 'q')\n")
    print("Write your question (To exit write 'salir', o 'exit', o 'q')\n")

    while True:
        # Escribimos la pregunta
        pregunta = input("> ").strip()

        # La formateamos para que no coja mayúsculas si vamos a salir
        if pregunta.lower() in {"salir", "exit", "q"}:
            break

        # Si no se escribe nada volvemos a indicar que se escriba pregunta
        if not pregunta:
            continue

        # Sacamos los 5 mejores chunks que nos devuelve el modelo (los que mejor responden a la pregunta)
        resultados = buscar(modelo, chunks, vectores, pregunta)

        # El llm nos genera la respuesta
        print("\nPensando...\n")
        respuesta = generar_respuesta(pregunta, resultados)

        # Indicamos la respuesta y los chunks usados
        for parrafo in respuesta.split("\n"):
            print(textwrap.fill(parrafo, width=88) if parrafo.strip() else "")
        print("\n--- Chunks usados ---")
        for r in resultados:
            print(f"  {r['similitud']:.3f}  {r['seccion']}")
        print()