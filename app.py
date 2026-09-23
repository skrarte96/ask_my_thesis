# Aplicación de streamlit con la estructura de preguntas y respuestas de la tesis
from pathlib import Path
import streamlit as st                              # Libreria de streamlit

from src.embed import cargar_modelo                 # Para cargar el LLM que se vaya a usar
from src.retrieve import cargar_indice, buscar      # Para cargar la tesis y buscar los chunks más adecuados
from src.generate import generar_respuesta_stream   # Nuestro generador de respuestas
import re                                           # Importamos regular expressions

RAIZ = Path(__file__).resolve().parent

# Título y subtítulo de la app
TITULO = "Ask My Thesis"
SUBTITULO = """¡Pregúntale a mi tesis! Hazle preguntas a mi tesis doctoral y ella te las contesta

*Ask My Thesis! Make questions to my PhD thesis and it will answer them*

**Electronic and optical properties of organic molecules at metal surfaces studied by scanning tunneling microscopy**

By Óscar Jover Arrate"""

# Modelo a emplear
MODELO_LLM = "qwen2.5:14b"
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
    if not latex_completo(trozo):
        return False
    return bool(RE_MARCADORES.search(trozo))
# Dejamos como solo texto las ecuaciones que aparezcan cortadas sin afectar a las demás
def sanear_latex(texto):
    # Troceamos el chunk
    partes = RE_DELIM.split(texto)
    salida = []
    # Vamos cacho a cacho del chunk
    for parte in partes:
        if parte in ("$", "$$"):
            continue
        # Si parece fórmula le devolvemos los $
        if parece_formula(parte):
            salida.append(f"${parte}$")
        else:
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
st.caption("Cada respuesta incluye las fuentes de la tesis: despliégalas para ver el texto original y las figuras.")
# Sacamos los chunks, vectores y el modelo
chunks, vectores, modelo = preparar()

# Creamos el historial si todavía no existe
if "historial" not in st.session_state:
    st.session_state.historial = []

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

# Creamos input donde sel usuario hará la pregunta
pregunta = st.chat_input("Pregunta algo sobre la tesis...")

# En caso de que se haya escrito algo, se guarda la pregunta
if pregunta:
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
            hueco.markdown("_Pensando/Thinking..._")     # _texto_ es cursiva

        # Metemos un generador
        def con_aviso():
            primero = True
            # Para cada trozo en generar respuesta en formato streaming
            for trozo in generar_respuesta_stream(pregunta, recuperados, modelo=MODELO_LLM):
                # Si es el primer token, quita el pensando del hueco y ya luego no lo pone más
                if primero:
                    hueco.empty()
                    primero = False
                yield trozo

        # Creamos contenedor para repintar la respuesta cuando la tengamos entera
        contenedor = st.empty()
        # Hacemos respuesta en streaming
        with contenedor:
            respuesta = st.write_stream(con_aviso())
        # La repasamos para corregir y la reprinteamos
        respuesta = sanear_latex(respuesta)
        contenedor.markdown(respuesta)

        # Creamos el desplegable con los chunks para esa pregunta
        mostrar_fuentes(recuperados)

    # Añadimos al historial la respuesta generada por el asistente
    st.session_state.historial.append({
        "rol": "assistant",
        "texto": respuesta,
        "fuentes": recuperados,
    })