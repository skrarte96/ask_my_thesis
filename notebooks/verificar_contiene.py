# Verificar
from pathlib import Path
import json

# Ruta raiz
RAIZ = Path(__file__).resolve().parent.parent

# Abrimos las preguntas
with open(RAIZ / "data" / "preguntas.json", encoding="utf-8") as f:
    casos = json.load(f)

# Abrimos los chunks de la tesis
with open(RAIZ / "data" / "processed" / "chunks.json", encoding="utf-8") as f:
    chunks = json.load(f)

# Cogemos las preguntas que tienen contiene
for caso in casos:
    dato = caso.get("contiene")
    if not dato:
        continue

    # Vemos qué chunks coinciden con el dato de contiene
    coincidencias = [c for c in chunks if dato in c["texto"]]

    # Si tenemos OK si hay chunks con el dato y NO si no
    marca = "OK " if coincidencias else "NO "
    # Marca si OK o No y lo que hay en contiene
    print(f"{marca} '{dato}'  →  {len(coincidencias)} chunks")

    # Si no hay coincidencia
    if not coincidencias:
        # Printea la pregunta
        print(f"      {caso['pregunta'][:]}")
    elif len(coincidencias) == 1:
        # Ruta donde estaba la coincidencia
        print(f"      en: {coincidencias[0]['seccion'][-55:]}")