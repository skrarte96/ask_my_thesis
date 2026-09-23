# Para ver donde no se están capturando las imágenes

from pathlib import Path
import json
import re

RAIZ = Path(__file__).resolve().parent.parent

RE_IMG = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

md = (RAIZ / "data" / "processed" / "tesis_limpia.md").read_text(encoding="utf-8")
todas = set(RE_IMG.findall(md))

with open(RAIZ / "data" / "processed" / "secciones.json", encoding="utf-8") as f:
    secciones = json.load(f)

capturadas = {i["ruta"] for s in secciones for i in s["imagenes"]}

print(f"En el markdown: {len(todas)}")
print(f"Capturadas:     {len(capturadas)}")
print(f"Perdidas:       {len(todas - capturadas)}\n")

for r in sorted(todas - capturadas):
    print("  ", r)