# Como no podemos cambiar el word, debemos hacer los arreglos a partir de un script de forma que cualquiera
# que se descargue el word original, pueda procesar el archivo de forma correcta.
# Quitamos los encabezados del archivo tesis.md a partir de la información que nos aporta word
# Librerias de rutas y regular expressions
from pathlib import Path
import re
# Leer documentos de .word
from docx import Document
# Rutas: RAIZ, raiz del proyecto; DOCX: donde está el word; ENTRADA: donde está nuestr tesis.md; SALIDA: donde guardaremos
# nuestra tesis procesada
RAIZ = Path(__file__).resolve().parent.parent
DOCX = RAIZ / "data" / "raw" / "electronic_and_optical_properties_of_organic_molecules_at_metal_surfaces_studied_by_scanning_tunneling_microscopy.docx"
ENTRADA = RAIZ / "data" / "processed" / "tesis.md"
SALIDA = RAIZ / "data" / "processed" / "tesis_limpia.md"

# Estilos sacados del word
ESTILOS = {"Heading 1": 1, "Heading 2": 2, "Heading 3": 3}

# Regular expressions para sacar los títulos de MD y los adornos que pone MarkDown para poder compararlos con el texto
# de word. Es decir detecta las [* ~ \ y '].
RE_TITULO_MD = re.compile(r"^(#{1,6})\s+(.*?)(?:\s*\{[^}]*\})?\s*$")
RE_ADORNOS = re.compile(r"[*~\\`]")
# Detecta líneas que presenten la estructura de una imagen (capturaremos su texto alternativo)
RE_ALT_IMAGEN = re.compile(r"^!\[([^\]]*)\]\([^)]*\)(\{[^}]*\})?\s*$")
# Detectar prefijos de estructuras de encabezados coladas entre el texto
RE_PREFIJO = re.compile(r"^(chapter \d+:|\d+(?:\.\d+)*)\s")
# Detectar las ecuaciones con erratas en word
RE_MATES_CIERRE = re.compile(r"(?<![\\$])\$(?!\$)([^$\n]+?)(?<!\\)\$(?!\$)(\)*)")

# Función que elimina los adornos de MarkDown
def normalizar(texto):
    texto = RE_ADORNOS.sub("", texto)
    return " ".join(texto.split()).lower()

# Función que detecta las cabeceras de imagen que estén metidas dentro del texto y no en líneas sueltas
def prefijo(texto):
    # Si hay match con nuestra regular expression que detecte el prefijo de una referencia a encabezado
    m = RE_PREFIJO.match(normalizar(texto))
    return m.group(1) if m else None
# Función que coge de cada párrafo, los textos que tengan por formato los puestos en nuestro diccionario ESTILOS,
# es decir, los títulos, subtítulos y secciones. De parámetro solo necesita la ruta
def encabezados_del_docx(ruta):
    # Cargamos el doc para que se lea y creamos un diccionario donde irán nuestros títulos
    doc = Document(ruta)
    titulos = {}

    # Para cada párrafo del documento si el estilo está en ESTILOS nos da el valor de ESTILOS correspondiente, si no,
    # nos devuelve None
    for p in doc.paragraphs:
        nivel = ESTILOS.get(p.style.name)
        # Adjuntamos texto, el texto del título
        texto = p.text.strip()

        # Si tenemos las dos cosas los incorporamos al diccionario
        if nivel and texto:
            titulos[normalizar(texto)] = (nivel, texto)

    return titulos

# Arreglamos los encabezados de word que nos salían mal al pasar con pandoc a Markdown
def arreglar(lineas, titulos):
    # Esto y el siguiente bucle for es para recoger todos los títulos que pandoc ha marcado bien
    marcados = set()
    # Crea un set con todos los prefijos para capturar encabezados entre el texto
    prefijos = set()
    for clave in titulos:
        p = prefijo(clave)
        if p:
            prefijos.add(p)
    # Pasamos por el Markdown una vez entera
    # Mete en marcados los títulos que pandoc sí ha encontrado
    for linea in lineas:
        m = RE_TITULO_MD.match(linea)
        if m:
            marcados.add(normalizar(m.group(2)))

    salida = []         # Markdown corregido que vamos construyendo (reconstruimos todo el texto)
    rescatados = set()  # Los encabezados perdidos que ya hemos recuperado
    eliminadas = 0      # Encabezados tirados que no necesitamos

    # Volvemos a pasar por todo el Markdown.
    for linea in lineas:
        # Si los títulos ya cuadran los adjuntamos a salida
        if RE_TITULO_MD.match(linea):
            salida.append(linea)
            continue

        # Si la línea es una imagen, sacamos el identificador de su texto alternativo
        m_img = RE_ALT_IMAGEN.match(linea)
        if m_img:
            p = prefijo(m_img.group(1))
            # Comprobamos si coincide con nuestros prefijos. Si lo hace, sustituimos la referencia, nos quedamos con
            # la imagen pero no con el texto alternativo
            if p and p in prefijos:
                salida.append(linea.replace(f"![{m_img.group(1)}]", "![]", 1))
                eliminadas += 1
                continue

        # Si no hay títulos los normalizamos (quitamos los adornos)
        clave = normalizar(linea)
        # Si la clave no está en los títulos leídos con Document, debe ser texto y lo pegamos tal cual
        if clave not in titulos:
            salida.append(linea)
            continue

        # Si la clave ya está en marcados o rescatados la eliminamos
        if clave in marcados or clave in rescatados:
            eliminadas += 1
            continue

        # Si la clave no está en marcados o rescatados es un título a poner, sacamos la info del diccionario que hemos
        # creado de titulos y la adjuntamos a salida con el formato de títulos de Markdown. También añadimos la clave al
        # set de rescatados
        nivel, texto = titulos[clave]
        salida.append(f"{'#' * nivel} {texto}")
        rescatados.add(clave)

    return salida, rescatados, eliminadas

# Repara las expresiones del word mal formuladas
def reparar_parentesis(linea):
    def arreglar(m):
        # Sacamos dividimos la fórmula entre lo que hay dentro de los $ y fuera
        dentro, cierres = m.group(1), m.group(2)
        # Resta el número de "(" al número de ")" si no es cero, faltan
        faltan = dentro.count("(") - dentro.count(")")

        # Si le falta a la fórmula al menos un paréntesis y los que faltan están fuera del $
        # Entonces si no faltan paréntesis y no hay fuera, se deja la fórmula como está
        if faltan <= 0 or len(cierres) < faltan:
            return m.group(0)

        # Se rehace la fórmula metiendo los paréntesis dentro que haga falta y quitando los de fuera
        sobran = len(cierres) - faltan
        return f"${dentro}{')' * faltan}${')' * sobran}"

    # Devuelve nuestra función arreglar para la línea que detecte la regular expression de fórmula
    return RE_MATES_CIERRE.sub(arreglar, linea)

if __name__ == "__main__":
    # Sacamos todos los encabezados del documento con Document
    titulos = encabezados_del_docx(DOCX)
    # Leemos el archivo Markdown a arreglar
    lineas = ENTRADA.read_text(encoding="utf-8").splitlines()
    # Sacamos las variables salida, rescatados y eliminadas de la función arreglar
    salida, rescatados, eliminadas = arreglar(lineas, titulos)

    # Arreglamos las ecuaciones rotas
    antes = "\n".join(salida)
    # Reparamos las fórmulas que hagan falta
    salida = [reparar_parentesis(l) for l in salida]
    # Vemos entre antes y al haber aplicado la función de reparar paréntesis, cuántas fórmulas hemos arreglado.
    # Las sumamos si antes es distinto de salida, (algo ha cambiado)
    reparadas = sum(1 for a, b in zip(antes.split("\n"), salida) if a != b)
    # Printeamos el número de fórmulas que han sido reparadas
    print(f"Líneas con fórmulas reparadas: {reparadas}")
    # Escribimos el archivo en la ruta de salida
    SALIDA.write_text("\n".join(salida), encoding="utf-8")

    # Printeamos info, los encabezados según el .docx, el número de rescatados y sus títulos así como el número de
    # cabeceras eliminadas y dónde se ha guardado (en que ruta) el Markdown limpio.
    print(f"Encabezados según el .docx: {len(titulos)}")
    print(f"Encabezados rescatados: {len(rescatados)}")
    for clave in rescatados:
        print(f"   {titulos[clave][1]}")
    print(f"\nCabeceras de página eliminadas: {eliminadas}")
    print(f"\nGuardado en: {SALIDA}")