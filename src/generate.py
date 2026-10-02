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
OLLAMA_MODELO = "qwen2.5:14b"

# Qué modelo usa cada backend si no se le dice otra cosa
MODELOS_POR_DEFECTO = {
    "ollama": OLLAMA_MODELO,
    "anthropic": "claude-haiku-4-5-20251001",
    "google": "gemini-3.6-flash",
}

# Nuestro tiempo que damos para que el modelo responda
TIMEOUT = 180

# Direcciones a las que mandamos las peticiones para anthropic y google
URL_ANTHROPIC = "https://api.anthropic.com/v1/messages"
URL_GOOGLE = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:{metodo}"

VERSION_ANTHROPIC = "2023-06-01"   # Versión del formato de la API, no del modelo
MAX_TOKENS = 4000                  # Techo de longitud de la respuesta (y de gasto)
TEMPERATURA = 0.2                  # La misma que usamos con Ollama creatividad vs rigidez
ESPERA = 120                       # Segundos de espera de la petición

# Metemos texto a los errores para que sean comprensibles por el usuario.
MENSAJES_HTTP = {
    401: "La clave de API no es válida. / The API key is not valid.",
    403: "La clave no tiene permiso para usar este modelo. / The key cannot use this model.",
    429: "Has superado el límite de peticiones o no te queda saldo. Prueba a cambiar "
         "de proveedor en la barra lateral. / Rate limit or no credit left. Try "
         "another provider in the sidebar.",
    500: "Error interno del proveedor. Inténtalo otra vez. / Provider error. Try again.",
    503: "El modelo está saturado. Inténtalo en unos segundos o cambia de proveedor "
     "en la barra lateral. / Model overloaded. Try again shortly or switch "
     "provider in the sidebar."
}

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
pregunta, INCLÚYELA literalmente en LaTeX. Usa $ para las expresiones en \
línea y $$ para las de bloque. NUNCA uses \\( \\) ni \\[ \\] como delimitadores.

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
bias voltage → voltaje bias, tunnelling → túnel.\
Scanning Tunneling Microscope → Microscopio de Efecto Túnel

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

# Las frases exactas con las que el modelo se abstiene. Tienen que coincidir
# palabra por palabra con las que se le piden en el prompt SISTEMA.
ABSTENCION = {
    "español": "Esa información no aparece en la tesis.",
    "inglés": "That information does not appear in the thesis.",
}

# True si la respuesta es una abstención o el mensaje de fallo, o sea si no hay
# nada que respaldar con fuentes
def es_abstencion(texto):
    limpio = texto.strip()
    frases = list(ABSTENCION.values()) + list(MENSAJE_FALLO.values())
    return any(limpio.startswith(f) for f in frases)

# Anthropic y Google reciben los mensajes de sistema y usuario por separado, así los deshacemos
def separar_mensajes(mensajes):
    # textos vacíos
    sistema = ""
    usuario = ""
    # Vamos mensaje a mensaje si es de system a sistema y todo lo demás a usuario
    for mensaje in mensajes:
        if mensaje["role"] == "system":
            sistema = mensaje["content"]
        else:
            usuario = mensaje["content"]
    # devolvemos tupla
    return sistema, usuario
# Creamos las peticiones desde aquí con el formato listo
def crear_peticion(url, cabeceras, cuerpo):
    datos = json.dumps(cuerpo).encode("utf-8")
    return urllib.request.Request(url, data=datos, headers=cabeceras, method="POST")
# Comprobamos si hay errores
def traducir_error(error):
    mensaje = MENSAJES_HTTP.get(error.code)
    # Si no es un error de los previstos, leemos lo que el servidor explica
    if mensaje is None:
        detalle = error.read().decode("utf-8", errors="replace")[:300]
        mensaje = f"El proveedor devolvió un error {error.code}. {detalle}"
    return RuntimeError(mensaje)
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

# ------------------ LLAMADAS A LOS LLMs -------------------------------
# Llamamos a Ollama creando la estructura .json que recibirá para la petición más Error Handling sobre el tiempo de
# respuesta de la petición. Si se pasa del tiempo TIMEOUT deja error de que no ha podido hablar con Ollama y pregunta si
# hemos corrido Ollama serve
def llamar_ollama(mensajes, modelo=OLLAMA_MODELO, url=OLLAMA_URL, clave=None):
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

# Llamamos a anthropic para crear la estructura de peticiones y respuesta
def llamar_anthropic(mensajes, modelo, clave=None):
    sistema, usuario = separar_mensajes(mensajes)
    cabeceras = {                                   # Como el remitente en una carta
        "x-api-key": clave,                         # Clave del usuario para acceder a anthropic
        "anthropic-version": VERSION_ANTHROPIC,     # Versión de la api de anthropic
        "content-type": "application/json",         # Indicamos que enviaremos un .json
    }
    cuerpo = {                                                  # Como el contenido de la carta
        "model": modelo,                                        # Nombre del modelo a usar de anthropic
        "max_tokens": MAX_TOKENS,                               # Máximo de tokens que hemos dicho de usar
        "temperature": TEMPERATURA,                             # Creatividad vs. rigidez
        "system": sistema,                                      # Instrucciones que damos, prompt de comportamiento
        "messages": [{"role": "user", "content": usuario}],     # Lista con la conversación, solo mandamos actual
                                                                # Modelo no conversacional, preguntas independientes
    }
    # Creamos la petición a mandar a anthropic
    peticion = crear_peticion(URL_ANTHROPIC, cabeceras, cuerpo)
    try:

        with urllib.request.urlopen(peticion, timeout=ESPERA) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8")) # traemos respuesta, decodificamos y convertimos a dicc
    except urllib.error.HTTPError as error:  # Vemos si hay error y si hay metemos nuestro mensaje técnico en terminal
        raise traducir_error(error) from error
    return "".join(bloque.get("text", "") for bloque in datos["content"])
# Llamamos a google para crear la estructura de peticiones y respuesta
def llamar_google(mensajes, modelo, clave=None):
    sistema, usuario = separar_mensajes(mensajes)
    url = URL_GOOGLE.format(modelo=modelo, metodo="generateContent")            # Peticiones de google
    cabeceras = {"x-goog-api-key": clave, "content-type": "application/json"}   # Cómo gestiona las cabeceras google
    cuerpo = {
        "system_instruction": {"parts": [{"text": sistema}]},
        "contents": [{"role": "user", "parts": [{"text": usuario}]}],
        "generationConfig": {"temperature": TEMPERATURA, "maxOutputTokens": MAX_TOKENS},  # Su formato de cuerpo
    }
    peticion = crear_peticion(url, cabeceras, cuerpo)                        # Creamos petición
    try:
        with urllib.request.urlopen(peticion, timeout=ESPERA) as respuesta:  # Enviamos petición
            datos = json.loads(respuesta.read().decode("utf-8"))             # Leemos, decodificamos y pasamos a diccion
    except urllib.error.HTTPError as error:                                  # Si hay error lo mostramos
        raise traducir_error(error) from error                               # Error Técnico en terminal
    partes = datos["candidates"][0]["content"]["parts"]                      # Sacamos la respuesta y la montamos (join)
    return "".join(parte.get("text", "") for parte in partes)

# ------------------ LLAMADAS A LOS LLMs EN STREAMING -------------------------------
# Llamamos a ollama para crear la estructura de peticiones y respuesta en streaming
def llamar_ollama_stream(mensajes, modelo=OLLAMA_MODELO, url=OLLAMA_URL, clave=None):
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
                # Si hay texto, lo suelta sobre la marcha
                if texto:
                    yield texto
                # Si llegamos al final de la respuesta, rompemos el bucle
                if trozo.get("done"):
                    break
    # En caso de que haya justo el tipo de error de conexión
    except urllib.error.URLError as e:
        # No hemos podido conectar con la URL y el error más probable será no haber conectado con Ollama (ollama serve)
        raise RuntimeError(
            f"No he podido hablar con Ollama en / Could not talk with Ollama in {url}. "
            f"¿Está corriendo 'ollama serve'? Detalle: / Is 'ollama serve' running? Detail {e}"
        )
# Es la capa de abstracción donde luego incorporaremos el resto de modelos que este proyecto aceptará
# De momento solo le guardamos la función de llamar a ollama como variable
# Llamamos a antrhopic para crear la estructura de peticiones y respuesta en streaming
def llamar_anthropic_stream(mensajes, modelo, clave=None):
    sistema, usuario = separar_mensajes(mensajes)
    cabeceras = {                                                       # Desde aquí
        "x-api-key": clave,                                             #
        "anthropic-version": VERSION_ANTHROPIC,                         #
        "content-type": "application/json",                             #
    }                                                                   #
    cuerpo = {                                                          #
        "model": modelo,                                                #
        "max_tokens": MAX_TOKENS,                                       #
        "temperature": TEMPERATURA,                                     #
        "system": sistema,                                              #
        "messages": [{"role": "user", "content": usuario}],             #
        "stream": True,                                                 # stream True. Recibir respuesta a cachos
    }                                                                   #
    peticion = crear_peticion(URL_ANTHROPIC, cabeceras, cuerpo)             # Creamos petición de post
    try:
        with urllib.request.urlopen(peticion, timeout=ESPERA) as respuesta: # Hacemos la petición y recibimos respuesta
            for linea in respuesta:                                     # Vamos línea por línea (streaming)
                linea = linea.decode("utf-8").strip()                   # Decodificamos
                if not linea.startswith("data: "):                      # Sacamos el bloque de datos
                    continue
                datos = json.loads(linea[6:])                           # Quitamos el texto 'data: '
                if datos.get("type") == "content_block_delta":          # Vamos al bloque del mensaje
                    texto = datos.get("delta", {}).get("text", "")      # Sacamos de los cambios, el texto generado
                    if texto:
                        yield texto                                     # Generador de la respuesta
    except urllib.error.HTTPError as error:                             # Si hay error
        raise traducir_error(error) from error                          # Nuestro mensaje de error, técnico en terminal
# Llamamos a antrhopic para crear la estructura de peticiones y respuesta en streaming
def llamar_google_stream(mensajes, modelo, clave=None):
    sistema, usuario = separar_mensajes(mensajes)
    # "?alt=sse" para que devuelva respuesta normal no la propia de google
    url = URL_GOOGLE.format(modelo=modelo, metodo="streamGenerateContent") + "?alt=sse"
    # Cabecera como llamar_google
    cabeceras = {"x-goog-api-key": clave, "content-type": "application/json"}
    # Mismo cuerpo que llamar_google
    cuerpo = {
        "system_instruction": {"parts": [{"text": sistema}]},
        "contents": [{"role": "user", "parts": [{"text": usuario}]}],
        "generationConfig": {"temperature": TEMPERATURA, "maxOutputTokens": MAX_TOKENS},
    }
    # Creamos petición
    peticion = crear_peticion(url, cabeceras, cuerpo)
    try:
        # Enviamos petición y sacamos respuesta
        with urllib.request.urlopen(peticion, timeout=ESPERA) as respuesta:
            # Línea por línea que es streaming
            for linea in respuesta:
                linea = linea.decode("utf-8").strip()
                # Quitamos las que no tienen data: (en data: vive la respuesta)
                if not linea.startswith("data: "):
                    continue
                # Quitamos los caracteres de 'data: ' solo queremos la respuesta
                datos = json.loads(linea[6:])
                # Google lanza varias respuestas, cogemos la primera
                for candidato in datos.get("candidates", []):
                    # sacamos el texto con la respuesta
                    for parte in candidato.get("content", {}).get("parts", []):
                        texto = parte.get("text", "")
                        if texto:
                            yield texto     # Generador con la respuesta
    # Si hay error lo sacamos aquí, la parte técnica en la terminal y en el programa nuestro mensaje
    except urllib.error.HTTPError as error:
        raise traducir_error(error) from error
# Es la capa de abstracción donde luego incorporaremos el resto de modelos que este proyecto aceptará
# De momento solo le guardamos la función de llamar a ollama como variable
BACKENDS = {
    "ollama": llamar_ollama,
    "anthropic": llamar_anthropic,
    "google": llamar_google,
}
# Diccionario con las funciones a llamar a los distintos modelos de stream
BACKENDS_STREAM = {
    "ollama": llamar_ollama_stream,
    "anthropic": llamar_anthropic_stream,
    "google": llamar_google_stream,
}
# Genera la respuesta para el modelo elegido
def generar_respuesta(pregunta, resultados, backend="ollama", modelo = None, clave=None):
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

    # Si no nos dicen modelo, usamos el que toque según el backend
    modelo = modelo or MODELOS_POR_DEFECTO[backend]
    respuesta = BACKENDS[backend](mensajes, modelo=modelo, clave=clave)

    # Metemos el mensaje de fallo en el idioma que toque si se desmadra el LLM
    if not respuesta_valida(respuesta):
        return MENSAJE_FALLO[idioma]

    return respuesta
# Genera respuestas para los modelos de streaming
def generar_respuesta_stream(pregunta, resultados, backend="ollama", modelo=None, clave=None):
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
    # Si no nos dicen modelo, actuamos con los predeterminados que tenemos para cada entidad (google, anthropic...)
    modelo = modelo or MODELOS_POR_DEFECTO[backend]
    trozos = BACKENDS_STREAM[backend](mensajes, modelo=modelo, clave=clave)
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