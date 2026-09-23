# Pequeño programa sin importancia solo para ver todas las fórmulas que hay en el Markdown de la tesis

from pathlib import Path
import re

RAIZ = Path(__file__).resolve().parent.parent
MD = RAIZ / "data" / "processed" / "tesis_limpia.md"

RE_BLOQUE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
RE_LINEA = re.compile(r"(?<!\$)\$([^$\n]+?)\$(?!\$)")

texto = MD.read_text(encoding="utf-8")

bloques = RE_BLOQUE.findall(texto)
sin_bloques = RE_BLOQUE.sub(" ", texto)
lineas = RE_LINEA.findall(sin_bloques)

print(f"Fórmulas de bloque ($$...$$): {len(bloques)}")
print(f"Fórmulas en línea ($...$):    {len(lineas)}")
print(f"Delimitadores $ en total:     {texto.count('$')}\n")

largos = sorted(bloques, key=len, reverse=True)

print("=== Las 10 fórmulas de bloque más largas ===\n")
for f in largos[:]:
    print(f"[{len(f)} car.]  {f.strip()}\n")

print("\n=== 10 fórmulas en línea de muestra ===\n")
for f in lineas[:]:
    print(f"[{len(f)} car.]  {f.strip()}")

todas = bloques + lineas
sin_llaves = [f for f in todas if "=" in f]

print(f"\n\n=== Fórmulas SIN llaves: {len(sin_llaves)} de {len(todas)} ===\n")
for f in sorted(sin_llaves, key=len, reverse=True):
    print(f"[{len(f):>4} car.]  {f.strip()}")