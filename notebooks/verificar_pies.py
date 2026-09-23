# Vemos si algún pie de imagen está repetido

from pathlib import Path
from collections import Counter
import json

RAIZ = Path(__file__).resolve().parent.parent

with open(RAIZ / "data" / "processed" / "secciones.json", encoding="utf-8") as f:
    secciones = json.load(f)

imagenes = [i for s in secciones for i in s["imagenes"]]

sin_pie = [i for i in imagenes if not i["pie"]]
print(f"Imágenes: {len(imagenes)}  ·  sin pie: {len(sin_pie)}\n")

pies = Counter(i["pie"][:70] for i in imagenes if i["pie"])

repetidos = {p: n for p, n in pies.items() if n > 1}

if repetidos:
    print(f"--- Pies asignados a varias imágenes ({len(repetidos)}) ---")
    for p, n in repetidos.items():
        print(f"{n}x  {p}")
else:
    print("Ningún pie está repetido")

print("\n--- Sin pie ---")
for i in sin_pie:
    print("  ", i["ruta"].split("/")[-1])