# Importamos rutas, para gestionar los .json, y statistics para sacar la media y mediana y plt para plotear
from pathlib import Path
import json
import statistics
import matplotlib.pyplot as plt

# Rutas de raiz, entrada del chunks.json de chunks.py y ruta de salida a crear la imagen
RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "data" / "processed" / "chunks.json"
SALIDA = RAIZ / "data" / "processed" / "distribucion_chunks.png"

# Cargamos el chunks.json
with open(ENTRADA, "r", encoding="utf-8") as f:
    chunks = json.load(f)

# Hacemos una comprehension list de las longitudes de los chunks
tamanos = [c["n"] for c in chunks]

# Calculamos medias, medianas, max y min
media = statistics.mean(tamanos)
mediana = statistics.median(tamanos)
minimo = min(tamanos)
maximo = max(tamanos)

# Hacemos el Histograma
fig, ax = plt.subplots(figsize=(10, 5))

ax.hist(tamanos, bins=30, color="mediumseagreen", edgecolor="white")

ax.axvline(media, color="crimson", linestyle="--", linewidth=2)
ax.axvline(mediana, color="royalblue", linestyle=":", linewidth=2)

ax.annotate(f"Media: {media:,.0f}",
            xy=(0.02, 0.94), xycoords="axes fraction",
            color="crimson", fontweight="bold")

ax.annotate(f"Mediana: {mediana:,.0f}",
            xy=(0.02, 0.88), xycoords="axes fraction",
            color="royalblue", fontweight="bold")

resumen = (f"Chunks: {len(chunks)}\n"
           f"Mínimo: {minimo:,}\n"
           f"Máximo: {maximo:,}")

ax.annotate(resumen,
            xy=(0.98, 0.94), xycoords="axes fraction",
            ha="right", va="top",
            color="dimgray",
            bbox=dict(boxstyle="round,pad=0.5",
                      facecolor="whitesmoke",
                      edgecolor="lightgray"))

ax.set_xlabel("Caracteres por chunk")
ax.set_ylabel("Número de chunks")
ax.set_title("Distribución del tamaño de los chunks")

plt.tight_layout()
plt.savefig(SALIDA, dpi=150)
plt.show()