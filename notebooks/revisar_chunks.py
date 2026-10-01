# Revisa chunks.json buscando problemas que romperán el renderizado en Streamlit
# o que le llegarán mal al modelo. No arregla nada: solo mide y enseña ejemplos.
from pathlib import Path
import json
import re

RAIZ = Path(__file__).resolve().parent.parent
CHUNKS = RAIZ / "data" / "processed" / "chunks.json"

# Un signo de dólar que NO forma parte de un $$
RE_DOLAR = re.compile(r"(?<!\$)\$(?!\$)")
# Fórmulas completas en línea, para mirarlas por dentro
RE_FORMULA = re.compile(r"(?<!\$)\$([^$\n]+?)\$(?!\$)")
# Letra o número pegado a una llave de apertura sin _ ni ^ delante.
# Los comandos de LaTeX (\frac, \sqrt, \int...) también acaban en letra pegada a una
# llave, así que los quitamos antes de buscar o salen todos como falsos positivos
RE_COMANDO = re.compile(r"\\[A-Za-z]+")
RE_SUBINDICE_PERDIDO = re.compile(r"(?<![_^{])[A-Za-z0-9]\{")


def subindice_perdido(formula):
    # Primero borramos los comandos, luego buscamos la huella del guion bajo robado
    limpia = RE_COMANDO.sub(" ", formula)
    return bool(RE_SUBINDICE_PERDIDO.search(limpia))


def dolares_impares(texto):
    """True si el chunk tiene un número impar de $, o sea una fórmula cortada."""
    return len(RE_DOLAR.findall(texto)) % 2 == 1


def bloques_impares(texto):
    """True si el chunk tiene un número impar de $$."""
    return texto.count("$$") % 2 == 1


def llaves_descuadradas(formula):
    """True si dentro de la fórmula no cuadran las llaves."""
    return formula.count("{") != formula.count("}")


def revisar(chunks):
    problemas = {
        "dolar_impar": [],
        "bloque_impar": [],
        "subindice_perdido": [],
        "llaves_descuadradas": [],
    }

    for c in chunks:
        texto = c["texto_limpio"]

        if dolares_impares(texto):
            problemas["dolar_impar"].append(c)

        if bloques_impares(texto):
            problemas["bloque_impar"].append(c)

        formulas = RE_FORMULA.findall(texto)

        if any(subindice_perdido(f) for f in formulas):
            problemas["subindice_perdido"].append(c)

        if any(llaves_descuadradas(f) for f in formulas):
            problemas["llaves_descuadradas"].append(c)

    return problemas


def imagenes_repetidas(chunks):
    """Cuenta cuántas veces aparece cada imagen repartida entre los chunks."""
    conteo = {}
    for c in chunks:
        for img in c.get("imagenes", []):
            conteo[img["ruta"]] = conteo.get(img["ruta"], 0) + 1
    return conteo


ETIQUETAS = {
    "dolar_impar": "Chunks con un $ suelto (fórmula cortada por el troceo)",
    "bloque_impar": "Chunks con un $$ suelto",
    "subindice_perdido": "Chunks con subíndices comidos (patrón 'k{2}')",
    "llaves_descuadradas": "Chunks con llaves sin cerrar dentro de una fórmula",
}

if __name__ == "__main__":
    with open(CHUNKS, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"\nChunks totales: {len(chunks)}\n")
    print("=" * 70)

    problemas = revisar(chunks)

    for clave, afectados in problemas.items():
        porcentaje = 100 * len(afectados) / len(chunks)
        print(f"\n{ETIQUETAS[clave]}")
        print(f"  {len(afectados)} de {len(chunks)}  ({porcentaje:.1f} %)")

        # Enseñamos dos ejemplos para poder verlo con los ojos
        for c in afectados[:2]:
            print(f"    · {c['id']}  {c['seccion'][:60]}")
            fragmento = " ".join(c["texto_limpio"].split())
            print(f"      {fragmento[:160]}...")

    print("\n" + "=" * 70)

    # Las imágenes se asignan por sección, así que se repiten en todos sus chunks
    conteo = imagenes_repetidas(chunks)
    if conteo:
        repetidas = sum(1 for n in conteo.values() if n > 1)
        maximo = max(conteo.values())
        print(f"\nImágenes distintas referenciadas: {len(conteo)}")
        print(f"  Repetidas en más de un chunk: {repetidas}")
        print(f"  La que más se repite aparece en {maximo} chunks")

    # Asteriscos de cursiva que se han quedado sin pareja al cortar el chunk
    RE_FORMULA_TODA = re.compile(r"\$\$.+?\$\$|\$[^$\n]+?\$", re.DOTALL)

    huerfanos = []
    for c in chunks:
        # Quitamos las fórmulas: dentro puede haber asteriscos que no son cursiva
        prosa = RE_FORMULA_TODA.sub(" ", c["texto_limpio"])
        # Si el número de asteriscos es impar, uno se quedó sin su pareja
        if prosa.count("*") % 2 == 1:
            huerfanos.append(c)

    print(f"\nChunks con un asterisco de cursiva sin pareja: {len(huerfanos)}")
    for c in huerfanos[:3]:
        print(f"   · {c['id']}  {c['seccion'][:60]}")
    print()