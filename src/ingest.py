# Importamps las librerías para las rutas, la gestion de archivos .json y las regular expressions
from pathlib import Path
import json
import re

# Sacamos las rutas: raiz del proyecto, entrada con la tesis en formato .md y salida a para las secciones.json
RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "data" / "processed" / "tesis_limpia.md"
SALIDA = RAIZ / "data" / "processed" / "secciones.json"

# Niveles de Título (#), Sección (##) y Subsección (###)
NIVELES = {"#": 0, "##": 1, "###": 2}

# Renombraremos contents por los acrónimos y constantes físicas que es con lo que nos vamos a quedar.
# Tenemos que quitar los contents para que el modelo no se confunda y vaya a los títulos del índice en vez de a los de
# la tesis que corresponden
RENOMBRAR = {"Contents": "Acronyms and Physical Constants"}

# EXPRESIONES REGULARES PARA CAPTAR LA INFORMACION QUE SE INDICA TRAS LA BARRABAJA _
# Para crear las secciones
RE_TITULO = re.compile(r"^(#{1,6})\s+(.+?)(?:\s*\{[^}]*\})?\s*$")
RE_LINEA_INDICE = re.compile(r"^\[.*\]\(#[^)]*\)\s*$")
RE_SEPARADOR = re.compile(r"^[\s\-|:=+]+$")

# Para sustituir el texto en .md por texto legible para un humano
RE_IMAGEN = re.compile(r"!\[(.*?)\]\([^)]*\)(?:\{[^}]*\})?", re.DOTALL)
RE_ENLACE = re.compile(r"\[([^\]]*)\]\(#[^)]*\)")
RE_ANCLA = re.compile(r"\[\]\{#[^}]*\}")
RE_ESCAPES = re.compile(r"\\([\[\]()])")

# Limpia las referencias de todo el texto dejando los títulos necesarios para que lo entienda un usuario.
#  Ej: [Figure 2.1](#_Ref126134829) ---> Figure 2.1
def limpiar(linea):
    linea = RE_IMAGEN.sub(r"\1", linea)
    linea = RE_ENLACE.sub(r"\1", linea)
    linea = RE_ANCLA.sub("", linea)
    linea = RE_ESCAPES.sub(r"\1", linea)
    return linea.strip()

# Función con la que crearemos nuestras secciones siendo los elementos de la lista diccionarios con la ruta y el texto
# de esa seccion
def extraer_secciones(ruta):
    # Lista vacía de secciones de texto a rellenar
    secciones = []
    # Aquí metemos la jerarquía de títulos, secciones y subsecciones, el diccionario de NIVELES arriba nos indica
    # los índices de la lista de jerarquía
    jerarquia = [None, None, None]

    # Lee línea por línea el archivo que haya en la ruta separado por sus correspondientes líneas.
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        # Ve si tenemos en esa línea un título segun nuestra regular expression
        coincidencia = RE_TITULO.match(linea)

        # En caso de que tengamos una coincidencia True
        if coincidencia:
            # Coge el número de almohadillas y saca su valor en el diccionario de NIVELES
            almohadillas = coincidencia.group(1)
            nivel = NIVELES.get(almohadillas)

            # En caso de que no haya niveles continúa a la siguiente línea del bucle
            if nivel is None:
                continue

            # Saca el texto del título (lo siguiente a las almohadillas)
            titulo = coincidencia.group(2).strip()
            # En caso de que haya algo o no en RENOMBRAR, lo cambia por el título que acabamos de sacar
            titulo = RENOMBRAR.get(titulo, titulo)

            # Metemos el título en la casilla de la lista de jerarquía que toca
            jerarquia[nivel] = titulo
            # En caso de que cambiemos de subsección o de título las jerarquías inferiores deben pasar a None
            for n in range(nivel + 1, 3):
                jerarquia[n] = None

            # Basicamente a nuestra lista de secciones (una lista de diccionarios) le metemos la lista con la ruta
            # y dejamos el espacio para el texto con los párrafos
            secciones.append({
                "ruta": [t for t in jerarquia if t],
                "parrafos": [],
            })
            continue
        # Tres razones seguidas, en caso de que encontremos que no haya nada en secciones (quitar todo lo que haya
        # antes del primer título de la tesis), que haya una línea del índice o una línea que sea de separación
        # pasamos olímpicamente de estas, solo queremos los títulos y los textos con sus fórmulas e imágenes
        if not secciones:
            continue

        if RE_LINEA_INDICE.match(linea):
            continue

        if RE_SEPARADOR.match(linea):
            continue

        # Si ha pasado todos los filtros anteriores, la línea debe ser texto y por ende habrá que limpiar formatos en
        # markdown para que pueda ser entendida por un humano
        texto = limpiar(linea)

        # Si de verdad tenemos texto (las anclas no tienen), lo incorporamos en secciones como el último párrafo
        if texto:
            secciones[-1]["parrafos"].append(texto)
    # Devolvemos todas las secciones que no tengan párrafos vacíos
    return [s for s in secciones if s["parrafos"]]

# Solo se ejecuta si corremos aquí el archivo o lo llamamos entero en otro con un import
if __name__ == "__main__":
    # Extraemos las funciones en nuestra ruta de entrada
    secciones = extraer_secciones(ENTRADA)

    # Creamos en la carpeta de la ruta de salida una carpeta (en caso de que no exista ya) donde guardaremos nuestro
    # archivo de secciones.json
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(secciones, f, ensure_ascii=False, indent=2)

    # Suma los caracteres totales de todos los párrafos sacados en secciones.json
    total = sum(len(" ".join(s["parrafos"])) for s in secciones)
    # Suma el número de secciones que tienen ecuaciones
    con_mates = sum(1 for s in secciones if "$" in " ".join(s["parrafos"]))

    # Info de todo lo que hemos ido sacando
    print(f"Secciones con contenido: {len(secciones)}")
    print(f"Caracteres totales: {total:,}")
    print(f"Secciones con ecuaciones: {con_mates}")
    print(f"\nGuardado en: {SALIDA}\n")

    # Enseña las tres primeras secciones con el número de párrafos y el de caracteres que presenta
    for s in secciones[:3]:
        print(" > ".join(s["ruta"]))
        print(f"   {len(s['parrafos'])} párrafos, {len(' '.join(s['parrafos']))} caracteres\n")