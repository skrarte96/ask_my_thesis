# Herramienta para explorar las fórmulas del Markdown de la tesis.
# Sirve para decidir qué caracteres sirven de marcador en RE_MARCADORES
# y qué longitud usar como umbral en parece_formula.
#
# Para filtrar, cambia las tres constantes de abajo y vuelve a lanzarlo.

from pathlib import Path
from collections import Counter
import re

RAIZ = Path(__file__).resolve().parent.parent
MD = RAIZ / "data" / "processed" / "tesis_limpia.md"

# ---------------- LO QUE QUIERES VER ----------------
# Cambia estas tres y vuelve a lanzar el script

EXCLUIR = []        # no muestres las que contengan ALGUNO de estos. Ej: ["=", "{"]
INCLUIR = []        # muestra solo las que contengan TODOS estos. Ej: ["\\frac"]
LARGO_MAX = None    # None = sin límite. Un número = solo las de ese largo o menos

# ----------------------------------------------------

# Los caracteres que estamos valorando como marcadores de "esto es una fórmula"
MARCADORES = ["{", "}", "\\", "=", "^", "_"]

RE_BLOQUE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
RE_LINEA = re.compile(r"(?<!\$)\$([^$\n]+?)\$(?!\$)")


def extraer(texto):
    """Saca las fórmulas de bloque y, del resto, las de línea."""
    bloques = RE_BLOQUE.findall(texto)
    # Quitamos las de bloque antes de buscar las de línea, o cazaríamos sus $ sueltos
    sin_bloques = RE_BLOQUE.sub(" ", texto)
    lineas = RE_LINEA.findall(sin_bloques)
    return bloques, lineas


def pasa_filtro(formula):
    """True si la fórmula cumple lo que pediste en las tres constantes de arriba."""
    if any(c in formula for c in EXCLUIR):
        return False
    if not all(c in formula for c in INCLUIR):
        return False
    if LARGO_MAX is not None and len(formula.strip()) > LARGO_MAX:
        return False
    return True


def tabla_marcadores(formulas):
    """Cuántas fórmulas contienen cada marcador."""
    print("\n=== CUÁNTAS FÓRMULAS CONTIENEN CADA MARCADOR ===\n")
    total = len(formulas)
    for c in MARCADORES:
        n = sum(1 for f in formulas if c in f)
        print(f"   {c!r:6} → {n:4} de {total}  ({100 * n / total:.1f} %)")


def sin_ningun_marcador(formulas):
    """Las fórmulas que no se salvarían con ningún marcador: son las que
    necesitan la regla de la longitud."""
    huerfanas = [f for f in formulas if not any(c in f for c in MARCADORES)]

    print(f"\n=== FÓRMULAS SIN NINGÚN MARCADOR: {len(huerfanas)} de {len(formulas)} ===")
    print("    (estas solo se pueden reconocer por su longitud)\n")

    if not huerfanas:
        print("   ninguna\n")
        return

    # Repartidas por longitud, para elegir el umbral con criterio
    largos = Counter(len(f.strip()) for f in huerfanas)
    print("   Longitud  Cuántas   Acumulado")
    acumulado = 0
    for largo in sorted(largos):
        acumulado += largos[largo]
        print(f"   {largo:>8}  {largos[largo]:>7}   {acumulado:>9} de {len(huerfanas)}")

    print("\n   Las más largas:\n")
    for f in sorted(huerfanas, key=len, reverse=True)[:15]:
        print(f"   [{len(f.strip()):>3} car.]  {f.strip()}")
    print()


if __name__ == "__main__":
    texto = MD.read_text(encoding="utf-8")
    bloques, lineas = extraer(texto)
    todas = bloques + lineas

    print(f"\nFórmulas de bloque ($$...$$): {len(bloques)}")
    print(f"Fórmulas en línea ($...$):    {len(lineas)}")
    print(f"Total:                        {len(todas)}")
    print(f"Delimitadores $ en el texto:  {texto.count('$')}")

    tabla_marcadores(todas)
    sin_ningun_marcador(todas)

    # Listado filtrado según las constantes de arriba
    filtradas = [f for f in todas if pasa_filtro(f)]

    print("=" * 70)
    print(f"\n=== LISTADO FILTRADO: {len(filtradas)} de {len(todas)} ===")
    print(f"    excluir={EXCLUIR}  incluir={INCLUIR}  largo_max={LARGO_MAX}\n")

    for f in sorted(filtradas, key=len, reverse=True):
        print(f"[{len(f.strip()):>4} car.]  {f.strip()}")
    print()