# Aplicación de streamlit con la estructura de preguntas y respuestas de la tesis
from pathlib import Path
import streamlit as st                                          # Libreria de streamlit

from src.embed import cargar_modelo                             # Para cargar el LLM que se vaya a usar
from src.retrieve import cargar_indice, buscar                  # Para cargar la tesis y buscar los chunks más adecuados
from src.generate import generar_respuesta_stream, es_abstencion  # Nuestro generador de respuestas y abstenciones
import re                                                       # Importamos regular expressions

RAIZ = Path(__file__).resolve().parent

# Título y subtítulo de la app
TITULO = "Ask My Thesis"
SUBTITULO = """¡Pregúntale a mi tesis! Hazle preguntas a mi tesis doctoral y ella te las contesta

*Ask My Thesis! Make questions to my PhD thesis and it will answer them*

"""
# Se despliega el resumen de la tesis
RESUMEN = """Esta tesis usa microscopía y espectroscopía de efecto túnel (STM/STS)
para estudiar la estructura electrónica de moléculas orgánicas depositadas sobre
superficies metálicas, y cómo esas moléculas alteran los plasmones de la nanocavidad
óptica que se forma entre la punta del microscopio y la muestra.
En la primera parte se caracterizan **por primera vez con STM** los orbitales
moleculares del fulertubo D5h(I)-C90 sobre Au(111), Ag(111) y NaCl/Ag(111),
distinguiendo dos familias: unos similares a los de un nanotubo de carbono y otros
similares a los de un fullereno.
En la segunda, las moléculas poliaromáticas planas BPEA y BPEN sobre Au(111) y
Ag(111) modifican sutilmente la distribución espectral de los modos plasmónicos,
cambios que se atribuyen a nuevos estados de interfase formados alrededor de las
moléculas.
En la tercera, con tetrafenilporfirinas metaladas, se encuentra un método para obtener
información óptica de moléculas adsorbidas directamente sobre metal, algo que se daba
por descartado por el apagado (*quenching*) de la luminiscencia molecular.

*This thesis uses scanning tunnelling microscopy and spectroscopy (STM/STS) to study
the electronic structure of organic molecules on metal surfaces, and how those
molecules alter the plasmons of the optical nanocavity formed between the microscope
tip and the sample.*
*The first part reports the first STM characterisation of the molecular orbitals of
the D5h(I)-C90 fullertube on Au(111), Ag(111) and NaCl/Ag(111), distinguishing two
families: carbon-nanotube-like and fullerene-like.*
*The second shows that the planar polyaromatic molecules BPEA and BPEN on Au(111) and
Ag(111) subtly reshape the spectral distribution of the plasmonic modes, changes
attributed to new interface states forming around the molecules.*
*The third, using metalated tetraphenyl porphyrins, finds a way to extract optical
information from molecules adsorbed directly on metal — long thought impossible
because of the quenching of molecular luminescence.*"""
# Modelo de ollama a emplear
MODELO_OLLAMA = "qwen2.5:14b"

# Número de chunks que devuelve
K = 5

# Regular expressions para captar ecuaciones que vienen en un bloque o en una línea. Con re.DOTALL cazamos saltos de
# línea que algunas ecuaciones pueden ocupar varias
RE_DELIM = re.compile(r"(\$\$|\$)")
RE_MARCADORES = re.compile(r"[{}\\=]|[\^_]\{")                # Si lleva esos caracteres dentro suponemos que es ecuación

RE_LEFT = re.compile(r"\\left")
RE_RIGHT = re.compile(r"\\right")
RE_BEGIN = re.compile(r"\\begin\{")
RE_END = re.compile(r"\\end\{")

# Capta los subíndices y superíndices de markdown que deberían ser de Latex
RE_SUB = re.compile(r"(?<=\w)~([^~\s]{1,12})~")
RE_SUP = re.compile(r"\^([^\^\s]{1,12})\^")

# El LLM a veces usa los delimitadores de LaTeX \( \) y \[ \] en vez de $ y $$.
# Son válidos en LaTeX pero Streamlit no los entiende, así que los traducimos.
# Esto normaliza lo que devuelve el modelo, que es una entrada externa que no controlamos.
RE_MATE_BLOQUE = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
RE_MATE_LINEA = re.compile(r"\\\((.+?)\\\)", re.DOTALL)

# En el caso de que los modelos no nos coloquen los $ de Latex y o hagan con otros delimitadores
# los sustituimos aquí por los $ para que Streamlit los pueda entender
def normalizar_delimitadores(texto):
    texto = RE_MATE_BLOQUE.sub(r"$$\1$$", texto)
    texto = RE_MATE_LINEA.sub(r"$\1$", texto)
    return texto

# Cambia los subíndices y superíndices de markdown a latex
def traducir_indices(trozo):
    trozo = RE_SUB.sub(r"$_{\1}$", trozo)
    trozo = RE_SUP.sub(r"$^{\1}$", trozo)
    return trozo
def latex_completo(trozo):
    if len(RE_LEFT.findall(trozo)) != len(RE_RIGHT.findall(trozo)):
        return False
    if len(RE_BEGIN.findall(trozo)) != len(RE_END.findall(trozo)):
        return False
    if trozo.count("{") != trozo.count("}"):
        return False
    return True
# Que nos devuelva un booleano, si lo consideramos fórmula o no
def parece_formula(trozo):
    trozo = trozo.strip()

    # Un trozo vacío no es una fórmula: evitamos generar un $$ suelto
    if not trozo:
        return False

    # Checkeamos que tenga todos los trozos de la fórmula
    if not latex_completo(trozo):
        return False

    # Un símbolo o una unidad sueltos ($E$, $L$, $pA$, $k_1$) son notación
    # matemática aunque no lleven llaves ni barras: van en cursiva matemática
    # Nuestra fórmula más larga solo detectable por longitud es de 12 caracteres
    if len(trozo) <= 12:
        return True

    return bool(RE_MARCADORES.search(trozo))
# Dejamos como solo texto las ecuaciones que aparezcan cortadas sin afectar a las demás
def sanear_latex(texto):
    # Troceamos el texto por los $ o $$
    partes = RE_DELIM.split(texto)
    salida = []
    dentro = False                      # Si True, el trozo iba entre $ o $$

    # Vamos para cada uno de los trozos partidos
    for parte in partes:
        # Usamos este if para contabilizar, cada vez que se encuentra un $ o $$ lo cambia y vemos la alternancia
        # entre, está dentro de una fórmula y no
        if parte in ("$", "$$"):
            dentro = not dentro         # cada delimitador cambia el estado así sabemos cuando estamos en fórmula o no
            continue

        if dentro:
            # Venía entre $: se los devolvemos solo si es LaTeX válido.
            # Si estaba roto, se queda como texto plano
            salida.append(f"${parte}$" if parece_formula(parte) else parte)
        else:
            # Era prosa: nunca se convierte en fórmula
            salida.append(traducir_indices(parte))

    return "".join(salida)
# Cómo mostramos el desplegable con desplegables de cada una de las fuentes
def mostrar_fuentes(fuentes):
    # Desplegable de fuentes
    with st.expander(f"Fuentes/Sources ({len(fuentes)} fragmentos/fragments)"):
        # Sacamos la última parte de la ruta, la más indicativa
        for i, f in enumerate(fuentes, 1):
            ruta = f["seccion"].split(" > ")
            titulo = traducir_indices(ruta[-1])

            # Colocamos para cada chunk recuerado su propio expander con todo el texto
            with st.expander(f"{i}. {titulo}  ·  {f['similitud']:.3f}"):
                st.caption(traducir_indices(" › ".join(ruta)))
                st.markdown(sanear_latex(f["texto"]))

                for img in f.get("imagenes", []):
                    ruta_img = RAIZ / img["ruta"]
                    if ruta_img.exists():
                        st.image(
                            str(ruta_img),
                            caption=traducir_indices(img["pie"]) or None,
                        )
# Cargamos una sola vez (@st.cache_resource()) los chunks, vectores y el modelo
@st.cache_resource(show_spinner="Cargando tesis / Loading thesis...")
def preparar():
    chunks, vectores = cargar_indice()
    modelo = cargar_modelo()
    return chunks, vectores, modelo

# Configuramos página, como será un chat, los cuadros de texto centrados y estrechos
st.set_page_config(page_title=TITULO, page_icon="📖", layout="centered")
# Parámetros de markdown para permitir el desplazamiento horizontal de texto y fórmulas
# Ajustamos el display de las fórmulas de forma que si son largas se pueda desplazar el texto
# overflow-x: sale barra para desplazarnos en horizontal
# overflow-y: hidden, evitamos que salga barra vertical
# padding-bottom: dejamos algo de espacio para que la barra de desplazamiento no tape la fórmula
# [data-testid="stExpander"] Para los despliegues
# display: inline-block caja para desplazar la fórmula en la línea de texto
# max-width: 100% que no se salga del recuadro
# vertical-align: middle al convertirla en caja, se desalinea del texto que la rodea y centramos la ecuación al medio
st.markdown("""
<style>
.katex-display {
    overflow-x: auto;
    overflow-y: hidden;
    padding-bottom: 0.5rem;
}

[data-testid="stExpander"] .katex {
    overflow-x: auto;
    overflow-y: hidden;
    display: inline-block;
    max-width: 100%;
    vertical-align: middle;
}

[data-testid="stExpander"] div[data-testid="stMarkdownContainer"] {
    overflow-x: auto;
}
</style>
""", unsafe_allow_html=True)     # Hemos metido nosotros esto en el HTML así que no pasa nada porque no lo escape
# Añadimos título y subtítulo
st.title(TITULO)
st.markdown(SUBTITULO)

# Creamos el historial si todavía no existe
if "historial" not in st.session_state:
    st.session_state.historial = []

# Preguntas de ejemplo para quien llega sin saber de qué va la tesis
EJEMPLOS = [
    "¿De qué trata la tesis?",
    "¿Qué es el efecto túnel cuántico?",
    "¿Qué moléculas se estudian y sobre qué superficies?",
]

# Guardamos aquí la pregunta si el visitante pulsa uno de los botones
if "sugerida" not in st.session_state:
    st.session_state.sugerida = None

# Enseñamos primero la portada de la tesis
portada = RAIZ / "data" / "media" / "portada.jpg"
if portada.exists():
    izq, centro, der = st.columns([1, 2, 1])
    with centro:
        st.image(str(portada))
# Luego el resumen
st.markdown(RESUMEN)
# Hueco solo para las sugerencias: estas sí desaparecen al usar una
hueco_sugerencias = st.empty()

if not st.session_state.historial:
    with hueco_sugerencias.container():
        st.caption("Prueba con una de estas / Try one of these:")
        for i, ejemplo in enumerate(EJEMPLOS):
            if st.button(ejemplo, key=f"ejemplo_{i}", use_container_width=True):
                st.session_state.sugerida = ejemplo

# Creamos lista de los proveedores de modelos, la key los que se verán en Streamlit y el value los que necesitamos
# para que nuestros modelos funcionen
PROVEEDORES = {
    "Google Gemini": "google",
    "Anthropic Claude": "anthropic",
    "Ollama (solo en local)": "ollama",
}

# Enlaces a nombrar donde se debe conseguir la clave API para Google y Anthropic
ENLACES = {
    "google": "https://aistudio.google.com/apikey",
    "anthropic": "https://console.anthropic.com/settings/keys",
}

# Estructura del despliegue de modelos
with st.sidebar:
    # Título, los modelos
    st.header("Modelo / Model")

    # Caja con los modelos a elegir
    etiqueta = st.selectbox("Proveedor / Provider", list(PROVEEDORES))
    # Colocamos el modelo elegido en backend para usarlo
    backend = PROVEEDORES[etiqueta]

    # Si el backend es ollama, como necesitamos clave por el argumento en nuestra función de generate.py
    # ponemos clave = None, aparte, mencionamos que ollama debería estar corriendo en el ordenador
    # Indicamos peso y modelo empleados por nosotros por ética
    if backend == "ollama":
        clave = None
        st.caption(
            "Solo funciona en local, con el repositorio clonado y Ollama corriendo. "
            "El modelo es `qwen2.5:14b`, unos 9 GB de descarga:\n\n"
            "`ollama pull qwen2.5:14b` y luego `ollama serve`\n\n"
            "*Local only: clone the repo and run Ollama. Model: qwen2.5:14b (~9 GB).*"
        )
    # En caso de que sea un modelo distinto a ollama tendremos que pedir la API key.
    # Indicamos donde se consigue y que solo se usa durante tu visita y no se guarda en ningún lado
    else:
        clave = st.text_input("Tu clave de API / Your API key", type="password")
        st.caption(f"Consíguela en / Get one at: {ENLACES[backend]}")
        st.caption(
            "Se usa solo durante tu visita: no se guarda ni se registra en ningún sitio. / "
            "Used only during your visit: never stored, never logged."
        )
    st.divider()
    st.caption(
        "Tesis/Thesis: [10.5281/zenodo.22911361](https://doi.org/10.5281/zenodo.22911361)  \n"
        "Código/Code: [GitHub](https://github.com/skrarte96/ask_my_thesis)"
    )

# Sacamos los chunks, vectores y el modelo
chunks, vectores, modelo = preparar()

# Directamente, forzamos a que si tenemos el modelo de ollama elegido se escoja el modelo que tenemos descargado
modelo_llm = MODELO_OLLAMA if backend == "ollama" else None

# Como con cada interacción se nos reejecuta todo, tenemos que repintar toda la conversación
# Cogemos los turnos de conversación guardados
for turno in st.session_state.historial:
    # Creamos las burbujas de chat para el rol del hablante (si user o assistant)
    with st.chat_message(turno["rol"]):
        # Printeamos la conversación
        st.markdown(turno["texto"])

        # Las preguntas de usuario no contienen las fuentes pero las respuestas sí. Las ponemos como desplegable
        if turno.get("fuentes"):
            # Hacemos desplegable de chunks
            mostrar_fuentes(turno["fuentes"])

# Creamos input donde el usuario hará la pregunta o escoge una de las preguntas sugeridas
pregunta = st.chat_input("Pregunta algo sobre la tesis...") or st.session_state.sugerida
st.session_state.sugerida = None      # se consume una sola vez

# En caso de que se haya escrito algo, se guarda la pregunta
if pregunta:
    # Quitamos las sugerencias en cuanto hay una pregunta
    hueco_sugerencias.empty()
    # En caso de que tengamos elegido un modelo distinto de ollama pero no tengamos clave API, damos mensaje de error
    if backend != "ollama" and not clave:
        st.warning(
            "Introduce tu clave de API en la barra lateral. / "
            "Enter your API key in the sidebar."
        )
        st.stop()
    st.session_state.historial.append({"rol": "user", "texto": pregunta})
    # Desde la perspectiva de chat de user de streamlit, se escribe la pregunta
    with st.chat_message("user"):
        st.markdown(pregunta)
    # Desde la perspectiva de chat del asistente se escribe la respuesta
    with st.chat_message("assistant"):
        # Ponemos spinners que indiquen lo que está pasando y que sean spinners para que desaparezcan al terminar
        # Para buscar los chunks en la tesis
        with st.spinner("Buscando en la tesis..."):
            recuperados = buscar(modelo, chunks, vectores, pregunta, k=K)
            # Creamos un hueco para escribir indicar que el programa está corriendo y no parado
            hueco = st.empty()
            hueco.markdown("_Pensando /Thinking..._")     # _texto_ es cursiva

        # Metemos un generador
        def con_aviso():
            primero = True
            # Para cada trozo en generar respuesta en formato streaming
            for trozo in generar_respuesta_stream(
                    pregunta,               # Pregunta del usuario
                    recuperados,            # Chunks de la tesis recuperados
                    backend=backend,        # Proveedor elegido en la barra lateral
                    modelo=modelo_llm,      # modelo a usar
                    clave=clave             # API key que ha insertado el usuario
            ):
                # Si es el primer token, quita el pensando del hueco y ya luego no lo pone más
                if primero:
                    hueco.empty()
                    primero = False
                yield trozo

        # Creamos contenedor para repintar la respuesta cuando la tengamos entera
        contenedor = st.empty()
        # Hacemos respuesta en streaming y con error handling
        try:
            with contenedor:
                # Aquí es donde hacemos verdaderamente la petición
                respuesta = st.write_stream(con_aviso())
        except RuntimeError as error:
            hueco.empty()           # Quitamos el "Pensando..." o se queda ahí colgado
            st.error(str(error))    # Printeamos el error en la app
            st.stop()               # Paramos la app

        # La repasamos para corregir y la reprinteamos
        respuesta = sanear_latex(normalizar_delimitadores(respuesta))


        contenedor.markdown(respuesta)

        # Creamos el desplegable con los chunks para esa pregunta
        # Si el modelo se ha abstenido no hay nada que respaldar, así que no
        # enseñamos fuentes: contradiría la propia respuesta
        if not es_abstencion(respuesta):
            mostrar_fuentes(recuperados)

    # Añadimos al historial la respuesta generada por el asistente
    st.session_state.historial.append({
        "rol": "assistant",
        "texto": respuesta,
        "fuentes": [] if es_abstencion(respuesta) else recuperados,
    })
# Aviso al pie: al ir el último, se pinta justo encima del cuadro de escribir
st.caption(
    "Las respuestas las genera un modelo de lenguaje a partir del texto de la tesis "
    "y pueden contener errores. Despliega las fuentes de cada respuesta para ver el "
    "fragmento original y sus figuras.  \n"
    "*Answers are generated by a language model from the thesis text and may contain "
    "errors. Open the sources under each answer to see the original fragment.*"
)