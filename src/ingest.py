# Importamos librerías de rutas
from pathlib import Path
# Importamos librería json para abrir y leer archivos de dicho tipo
import json
# Importamos Document para leer el word con la tesis
from docx import Document

# Vamos hasta el file path raiz
RAIZ = Path(__file__).resolve().parent.parent
# Cogemos la ruta donde está el word con la tesis
RUTA = RAIZ / "data" / "raw" / "electronic_and_optical_properties_of_organic_molecules_at_metal_surfaces_studied_by_scanning_tunneling_microscopy_oscar_jover_arrate_phd_thesis.docx"
# Creamos archivo json con el word separado en secciones
SALIDA = RAIZ / "data" / "processed" / "secciones.json"

# Dic con los estilos de título. Marcarán las posiciones de la lista jerarquía más abajo
ESTILOS_TITULO = {"Heading 1": 0, "Heading 2": 1, "Heading 3": 2}

# Set con los estilos de text que queremos conservar
ESTILOS_CONTENIDO = {
    "Normal", "Body Text", "Normal (Web)", "List Paragraph",
    "Caption", "VA_Figure_Caption",
}

# Set con los estilos de texto que queremos ignorar
ESTILOS_IGNORAR = {"table of figures"}

# Devuelve una lista de los elementos de la lista secciones. cada elemento tiene la ruta a la que pertenece y una lista
# con los textos que pertenecen a esa ruta. por ruta nos referimos a la subsección de la tesis en la que estamos.
def extraer_secciones(ruta):
    # Cargamos la tesis en doc
    doc = Document(ruta)
    # Lista vacía para crear una lista de secciones de texto de la tesis
    secciones = []
    # Tres huecos para cada uno de los tres niveles de títulos definidos en ESTILO_TITULO.
    # Aquí guardaremos donde nos encontramos exactamente. jerarquía[0] -> capítulo, jerarquía[1] -> sección y jerarquía[2] -> subsección
    jerarquia = [None, None, None]

    # Iteramos sobre todos los párrafos del documento
    for p in doc.paragraphs:
        # Quitamos de cada párrafo los espacios y saltos de línea
        texto = p.text.strip()
        # Guardamos el estilo en la var estilo (si es heading, list paragraph, caption...)
        estilo = p.style.name

        # Si texto está vacío o el estilo está en los estilos que queremos ignorar continúa sigue a la siguiente iteración
        # Si es otra cosa salta al siguiente if
        if not texto or estilo in ESTILOS_IGNORAR:
            continue

        # Si el estilo de la p actual es de los de título
        if estilo in ESTILOS_TITULO:
            # Sacamos el nivel (número) del estilo de texto
            nivel = ESTILOS_TITULO[estilo]
            # Colocamos el título de texto en el índice de jerarquía correspondiente.
            jerarquia[nivel] = texto
            # Borra de jerarquía aquellos subniveles de donde se ha producido un cambio. Ejemplo, si cambiamos a una
            # sección nueva, se pone None la subsección jerarquia[2]. Y si cambiamos a un capítulo nuevo, se pone None tanto la sección
            # como la subsección jerarquia[1] y jerarquia[2]
            for n in range(nivel + 1, 3):
                jerarquia[n] = None
            # En la lista secciones mete un diccionario. la ruta donde estamos y una lista vacía donde irán los textos
            secciones.append({
                "ruta": [t for t in jerarquia if t],
                "parrafos": [],
            })
        # En el caso de que no hubiésemos tenido un título sino otra cosa por ejemplo cuerpo del párrafo (texto)
        elif estilo in ESTILOS_CONTENIDO:
            # En caso de que secciones no esté vacío se activa este if que, en la lista párrafos de secciones, en la última
            # casilla de la lista, mete los textos que vayan perteneciendo a esa sección de la tesis
            if secciones:
                secciones[-1]["parrafos"].append(texto)
    # En caso de que haya texto en los párrafos y no sean None, devuelve una lista de todos los elementos guardados en secciones
    return [s for s in secciones if s["parrafos"]]

# De modo que esta parte del script solo se ejecute cuando la corremos directamente. Así podemos rescatar la función para
# extraer_secciones() de arriba para otros scripts
if __name__ == "__main__":
    # Sacamos las secciones con sus rutas en el texto y el texto dentro de cada ruta (párrafos de la tesis)
    secciones = extraer_secciones(RUTA)

    # Crea las carpetas que hay en SALIDA, la cual definimos antes y apunta a data/processed/secciones.json
    # Crea los parents que hagan falta. Carpetas intermedias con parents = True
    # En caso de que ya existan no hace nada (exist_ok = True) si no estuviera esto daría error
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    # En la ruta de SALIDA, escribe el archivo json. código utf-8
    with open(SALIDA, "w", encoding="utf-8") as f:
        # Se escriben las secciones en el archivo f. Escribe las tildes como tal para que no se lean con código raro
        # Con indent 2 sangra dos espacios por nivel. Así no escribe una línea kilométrica y podemos revisar el archivo una
        # vez creado
        json.dump(secciones, f, ensure_ascii=False, indent=2)

    # Printeamos informe de lo que se ha hecho
    # Suma el número de caracteres que tienen todas las secciones juntas e indica donde los guarda (en la ruta SALIDA)
    total = sum(len(" ".join(s["parrafos"])) for s in secciones)
    print(f"Secciones con contenido: {len(secciones)}")
    print(f"Caracteres totales: {total:,}")
    print(f"\nGuardado en: {SALIDA}\n")

    # Vemos las tres primeras secciones
    for s in secciones[:3]:
        print(" > ".join(s["ruta"]))
        print(f"   {len(s['parrafos'])} párrafos, {len(' '.join(s['parrafos']))} caracteres\n")