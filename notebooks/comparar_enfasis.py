# Separa secciones.json en zonas de FORMULA (lo que va entre $ o $$) y zonas de
# PROSA (todo lo demás), y cuenta las rachas de * y de _ en cada zona según su
# longitud (1, 2, 3 o mas).
#
# Sirve para responder una sola pregunta: si cambiamos {1,3} por {2,3} en
# RE_ENFASIS, ¿dejamos de romper formulas sin perder limpieza de prosa?
from pathlib import Path
import json
import re
from collections import Counter

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "data" / "processed" / "secciones.json"

# Cualquier formula: primero las de bloque $$...$$, luego las de linea $...$
RE_FORMULA = re.compile(r"\$\$.+?\$\$|\$[^$\n]+?\$", re.DOTALL)

# Rachas seguidas del mismo simbolo. El + coge la racha entera, asi sabemos
# si son uno, dos o tres seguidos
RE_RACHA = re.compile(r"\*+|_+")


def separar(texto):
    """Devuelve dos listas de trozos: los que son formula y los que son prosa."""
    formulas = []
    prosa = []
    fin_anterior = 0

    for m in RE_FORMULA.finditer(texto):
        # Lo que hay entre el final de la formula anterior y el principio de esta es prosa
        prosa.append(texto[fin_anterior:m.start()])
        formulas.append(m.group(0))
        fin_anterior = m.end()

    # La cola que queda despues de la ultima formula tambien es prosa
    prosa.append(texto[fin_anterior:])

    return formulas, prosa


def contar_rachas(trozos):
    """Cuenta las rachas de * y _ por simbolo y longitud. Guarda ejemplos."""
    conteo = Counter()
    ejemplos = {}

    for trozo in trozos:
        for m in RE_RACHA.finditer(trozo):
            racha = m.group(0)
            simbolo = racha[0]           # '*' o '_'
            largo = len(racha)           # 1, 2, 3, ...
            # Agrupamos los de 4 o mas en una sola categoria, son rarezas
            etiqueta = (simbolo, largo if largo <= 3 else 4)
            conteo[etiqueta] += 1

            # Nos quedamos con un ejemplo de cada tipo para poder mirarlo
            if etiqueta not in ejemplos:
                alrededor = trozo[max(0, m.start() - 40):m.end() + 40]
                ejemplos[etiqueta] = " ".join(alrededor.split())

    return conteo, ejemplos


def imprimir(titulo, conteo, ejemplos):
    print(f"\n{titulo}")
    print("-" * 70)

    if not conteo:
        print("   (ninguna racha de * ni de _)")
        return

    for simbolo in ("*", "_"):
        for largo in (1, 2, 3, 4):
            n = conteo.get((simbolo, largo), 0)
            if not n:
                continue
            nombre = simbolo * largo if largo <= 3 else f"{simbolo} x4 o mas"
            print(f"   {nombre:12} → {n}")
            print(f"        ej: {ejemplos[(simbolo, largo)][:100]}")


if __name__ == "__main__":
    with open(ENTRADA, "r", encoding="utf-8") as f:
        secciones = json.load(f)

    todas_formulas = []
    toda_prosa = []

    for s in secciones:
        texto = "\n".join(s["parrafos"])
        formulas, prosa = separar(texto)
        todas_formulas.extend(formulas)
        toda_prosa.extend(prosa)

    print(f"\nSecciones: {len(secciones)}   Formulas encontradas: {len(todas_formulas)}")
    print("=" * 70)

    conteo_f, ejemplos_f = contar_rachas(todas_formulas)
    conteo_p, ejemplos_p = contar_rachas(toda_prosa)

    imprimir("DENTRO DE FORMULAS", conteo_f, ejemplos_f)
    imprimir("EN PROSA", conteo_p, ejemplos_p)

    # ----- El veredicto -----
    # Sueltos = rachas de longitud 1. Son los que {1,3} toca y {2,3} no tocaria.
    sueltos_f = conteo_f.get(("*", 1), 0) + conteo_f.get(("_", 1), 0)
    dobles_f = sum(n for (s, l), n in conteo_f.items() if l >= 2)

    sueltos_p = conteo_p.get(("*", 1), 0) + conteo_p.get(("_", 1), 0)
    dobles_p = sum(n for (s, l), n in conteo_p.items() if l >= 2)

    print("\n" + "=" * 70)
    print("\nVEREDICTO\n")
    print(f"  Con {{1,3}} (el actual):")
    print(f"     rompe {sueltos_f + dobles_f} sitios dentro de formulas")
    print(f"     limpia {sueltos_p + dobles_p} sitios de prosa")
    print()
    print(f"  Con {{2,3}} (el propuesto):")
    print(f"     rompe {dobles_f} sitios dentro de formulas")
    print(f"     limpia {dobles_p} sitios de prosa")
    print()

    if dobles_f == 0:
        print("  → {2,3} NO toca ninguna formula. Cambio seguro.")
    else:
        print(f"  → CUIDADO: hay {dobles_f} rachas de 2 o 3 dentro de formulas.")
        print("    Mira los ejemplos de arriba antes de cambiar nada.")

    perdido = sueltos_p
    if perdido:
        print(f"  → Se dejarian de limpiar {perdido} cursivas sueltas en prosa.")
    else:
        print("  → No se pierde ninguna limpieza de prosa.")
    print()