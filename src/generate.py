# Esta será la capa de abstracción que gobierna entre backends y el prompt que gobierna cómo responde.
from pathlib import Path    # Rutas de Python
import json                 # Cargar y gestionar archivos .json
import textwrap             # Estructura de printeo de texto más human-friendly
# Hacer peticiones HTTP
import urllib.error         # Capturar fallos de red
import urllib.request       # Gestionar las peticiones
import re                   # Importamos regular expressions

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

Si NO la contienen, responde solo esta frase, en el idioma que se te indique, y \
nada más:
  español: "Esa información no aparece en la tesis."
  inglés: "That information does not appear in the thesis."

Nunca combines una respuesta con esa frase: o respondes, o te abstienes.

Si SÍ la contienen, sigue estas reglas:

SIGLAS: escribe STM, STS, LDOS, DOS, HOMO, LUMO, BPEA, BPEN, PdTPP, FeClTPP, \
CNT, SWCNT tal cual, en su forma original. Nunca inventes qué significan ni \
traduzcas nombres de moléculas, técnicas o materiales.

FÓRMULAS: si los fragmentos contienen una expresión matemática relevante para la \
pregunta, INCLÚYELA literalmente en LaTeX, entre $ o $$, tal y como aparece. Nunca \
te limites a referirte a ella ("según la Ecuación (23)", "como muestra la expresión \
(4)"): si la mencionas, escríbela.

DATOS: cada número y unidad debe aparecer en los fragmentos, referido a la misma \
magnitud. No reutilices un dato para algo distinto de aquello a lo que se refiere.

TONO: usa el registro tentativo propio de un texto científico. Escribe "esto \
sugiere", "los datos indican", "puede interpretarse como". Evita "esto demuestra" \
o "queda probado". Si los fragmentos plantean una hipótesis sin cerrarla, \
preséntala como hipótesis.

CITAS: al final de cada frase, entre corchetes, el número de la subsección. \
Ejemplo: "...decae exponencialmente con la distancia [2.3.3]." Si varios \
fragmentos son de la misma subsección, cítala UNA sola vez. Dentro del texto \
verás otros corchetes como [114]: son referencias bibliográficas, nunca las uses \
como cita de sección.

GLOSARIO (usa estas traducciones exactas): anthracene → antraceno, \
naphthalene → naftaleno, fullerenes → fullerenos, nanoribbons → nanocintas, \
fullertubes → fullertubos, annealing → annealing (no traducir), \
sputtering → sputtering (no traducir), luminescence → luminiscencia\
bias voltage → voltaje bias, tunnelling → túnel.

FORMA: prosa continua, sin títulos ni encabezados.

Antes de terminar, revisa que cada dato numérico está en los fragmentos y se \
refiere a lo mismo."""

# Tenemos que meterle el contexto y la pregunta. Luego los incorporamos con format
PLANTILLA = """Contexto extraído de la tesis:

{contexto}

---

Pregunta: {pregunta}

Responde en {idioma}."""

# Para detectar el idioma, si español o inglés

# Palabras clave para detectar si estamos preguntando en español
MARCAS_ES = set("áéíóúñ¿¡")

PALABRAS_ES = {
    "qué", "cómo", "cuál", "cuáles", "cuándo", "dónde", "por",
    "del", "las", "los", "una", "unos", "puedes", "hay", "entre",
    "son", "esta", "este", "esa", "ese", "para", "con", "sobre",
    "respecto", "diferencias", "fórmula", "valor", "el", "la", "un",
    "uno", "unas", "me", "te", "le", "nos",
    "que", "como", "cual", "cuales", "cuando", "donde", "por",
}


# Regular expression para detectar caracteres chinos
RE_CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")

# Mensaje a desplegar en caso de que el LLM se desmadre
MENSAJE_FALLO = {
    "español": "No he podido generar una respuesta fiable a esta pregunta.",
    "inglés": "I could not generate a reliable answer to this question.",
}

# En caso de que detecte caracteres chinos, que no los detecte. A veces el LLM falla y devuelve su idioma chino de
# fábrica
def respuesta_valida(texto):
    return not RE_CJK.search(texto)
# Revisa la pregunta en busca de palabras clave y elige el idioma de respuesta
def detectar_idioma(pregunta):
    texto = pregunta.lower()

    # Si detecta las palabras clave que hemos puesto en español, habla en español
    if any(c in MARCAS_ES for c in texto):
        return "español"

    palabras = set(texto.replace("?", " ").replace("¿", " ").split())
    if palabras & PALABRAS_ES:
        return "español"

    # Si no detectó nuestras palabras clave en español, responde en inglés
    return "inglés"

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
        "options": {
            "temperature": 0.2,           # 0 respuesta rígida, 1 respuesta muy creativa y puede divagar
            "stop": ["\nuser", "\nPregunta:", "\nQuestion:"],   # Para si detecta una de estas tres palabras
                },
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
            f"No he podido hablar con Ollama en / Could not talk with Ollama in {url}. "
            f"¿Está corriendo 'ollama serve'? Detalle: / Is 'ollama serve' running? Detail {e}"
        )

    # Del texto generado solo nos interesa el mensaje y el contenido
    return resultado["message"]["content"]

# Es la capa de abstracción donde luego incorporaremos el resto de modelos que este proyecto aceptará
# De momento solo le guardamos la función de llamar a ollama como variable
BACKENDS = {
    "ollama": llamar_ollama,
}

def llamar_ollama_stream(mensajes, modelo=OLLAMA_MODELO, url=OLLAMA_URL):
    # Igual que llamar_ollama pero con stream true
    cuerpo = {
        "model": modelo,
        "messages": mensajes,
        "stream": True,
        "options": {
            "temperature": 0.2,
            "stop": ["\nuser", "\nPregunta:", "\nQuestion:"],
        },
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
            # Vamos línea por línea según las va generando la respuesta
            for linea in respuesta:
                # Quitamos los espacions y los saltos
                if not linea.strip():
                    continue
                # La línea creada por el modelo la descodificamos y convertimos a diccionario
                trozo = json.loads(linea.decode("utf-8"))
                # Pedimos el mensaje (si no hay, da diccionario vacío, y de ahí dame el contenido (si no hay, nada)
                texto = trozo.get("message", {}).get("content", "")
                # Si llegamos al final de la respuesta, rompemos el bucle
                if trozo.get("done"):
                    break
                # Si hay texto, lo suelta sobre la marcha
                if texto:
                    yield texto
    # En caso de que haya justo el tipo de error de conexión
    except urllib.error.URLError as e:
        # No hemos podido conectar con la URL y el error más probable será no haber conectado con Ollama (ollama serve)
        raise RuntimeError(
            f"No he podido hablar con Ollama en / Could not talk with Ollama in {url}. "
            f"¿Está corriendo 'ollama serve'? Detalle: / Is 'ollama serve' running? Detail {e}"
        )
# Es la capa de abstracción donde luego incorporaremos el resto de modelos que este proyecto aceptará
# De momento solo le guardamos la función de llamar a ollama como variable
BACKENDS_STREAM = {
    "ollama": llamar_ollama_stream,
}
def generar_respuesta(pregunta, resultados, backend="ollama", modelo = None):
    # Primero que nada chequeamos si el backend a meter es el correcto (tenemos un modelo aceptado de los que carga)
    if backend not in BACKENDS:
        raise ValueError(
            f"Backend '{backend}' desconocido / unknown. Disponibles/Available: {list(BACKENDS)}"
        )

    # Detectamos idioma y formateamos el contexto
    idioma = detectar_idioma(pregunta)

    # Con los resultados obtenidos de antes (los 5 chunks generados en retrieve.py con la función buscar, formateamos
    # los 5 chunks para crear el contexto
    contexto = formatear_contexto(resultados)

    # Creamos la lista de mensajes a enviar al modelo, en este caso el prompt principal de comportamiento y luego la
    # plantilla con el contexto recogido y la pregunta del usuario
    mensajes = [
        {"role": "system", "content": SISTEMA},         # Da más importancia al ser role = system (aquí comportamiento)
        {"role": "user", "content": PLANTILLA.format(
            contexto=contexto,
            pregunta=pregunta,
            idioma=idioma,
        )},                                             # Contexto dado, pregunta del usuario e idioma de respuesta
    ]

    # Sacamos la función de BACKENDS (el modelo a llamar) y luego los mensajes con el prompt, contexto y pregunta
    if modelo:
        respuesta = BACKENDS[backend](mensajes, modelo=modelo)
    else:
        respuesta = BACKENDS[backend](mensajes)

    # Metemos el mensaje de fallo en el idioma que toque si se desmadra el LLM
    if not respuesta_valida(respuesta):
        return MENSAJE_FALLO[idioma]

    return respuesta

def generar_respuesta_stream(pregunta, resultados, backend="ollama", modelo=None):
    if backend not in BACKENDS_STREAM:
        raise ValueError(
            f"Backend '{backend}' no soporta streaming./Does not hold streaming "
            f"Disponibles/Available: {list(BACKENDS_STREAM)}"
        )
    # Detectamos idioma y formateamos el contexto
    idioma = detectar_idioma(pregunta)
    contexto = formatear_contexto(resultados)
    # Creamos la lista de mensajes a enviar al modelo, en este caso el prompt principal de comportamiento y luego la
    # plantilla con el contexto recogido y la pregunta del usuario
    mensajes = [
        {"role": "system", "content": SISTEMA},
        {"role": "user", "content": PLANTILLA.format(
            contexto=contexto,
            pregunta=pregunta,
            idioma=idioma,
        )},
    ]
    # Sacamos la función de BACKENDS (el modelo a llamar) y luego los mensajes con el prompt, contexto y pregunta
    if modelo:
        trozos = BACKENDS_STREAM[backend](mensajes, modelo=modelo)
    else:
        trozos = BACKENDS_STREAM[backend](mensajes)
    # Guardamos la respuesta entera en un texto mientras la vamos printeando palabra por palabra
    acumulado = ""
    for trozo in trozos:
        acumulado += trozo
        yield trozo
    # Si al final la respuesta no era válida (salen caracteres chinos) al final de la respuesta pone que no es válida
    if not respuesta_valida(acumulado):
        yield "\n\n---\n\n" + MENSAJE_FALLO[idioma]
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