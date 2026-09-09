# Importamos la librería para las rutas de python
from pathlib import Path
# Poder gestionar los archivos .json
import json
# Visualizaciones
import matplotlib.pyplot as plt
# Estadísticas
import statistics

# Sacamos la raíz del proyecto
RAIZ = Path(__file__).resolve().parent.parent
# Archivo de secciones creado en ingest.py que vamos a tratar
ENTRADA = RAIZ / "data" / "processed" / "secciones.json"

# Leemos nuestro archivo de secciones
with open(ENTRADA, "r", encoding="utf-8") as f:
    secciones = json.load(f)

# Añadimos clave n con las longitudes de secciones
for s in secciones:
    s["n"] = len(" ".join(s["parrafos"]))

# Secciones ordenadas por sus longitudes de mayor a menor
ordenadas = sorted(secciones, key=lambda s: s["n"], reverse=True)

# Vemos cuales son las 12 secciones más largas junto con sus rutas
print("--- Las 12 más largas ---")
for s in ordenadas[:12]:
    print(f"{s['n']:>7,}  {' > '.join(s['ruta'])}")

# Vemos aquí cuales son las 8 secciones más cortas junto con sus rutas
print("\n--- Las 8 más cortas ---")
for s in ordenadas[-8:]:
    print(f"{s['n']:>7,}  {' > '.join(s['ruta'])}")

# Ahora tenemos una lista de tamaños de las secciones.
tamanos = sorted(s["n"] for s in secciones)

# Visualización de la distribución de longitudes de secciones
# Media y mediana de la distribución de tamaños
media = statistics.mean(tamanos)
mediana = statistics.median(tamanos)

# Creamos figura a pintar
fig, ax = plt.subplots(figsize=(10, 5))

# Histograma de tamaños de las secciones
ax.hist(tamanos, bins=25, color="salmon", edgecolor="white")
# Línea vertical de la media
ax.axvline(media, color="royalblue", linestyle="--", linewidth=2)
# Línea vertical de la mediana
ax.axvline(mediana, color="seagreen", linestyle="--", linewidth=2)

# Anotación de la media
ax.annotate(f"Media: {media:,.0f}",
            xy=(media, ax.get_ylim()[1] * 0.9),
            xytext=(10, 0), textcoords="offset points",
            color="royalblue", fontweight="bold")

# Anotación de la mediana
ax.annotate(f"Mediana: {mediana:,.0f}",
            xy=(mediana, ax.get_ylim()[1] * 0.85),
            xytext=(20, 0), textcoords="offset points",
            color="seagreen", fontweight="bold")

ax.set_xlabel("Caracteres por sección")
ax.set_ylabel("Número de secciones")
ax.set_title("Distribución del tamaño de las secciones de la tesis")

plt.tight_layout()
plt.savefig(RAIZ / "data" / "processed" / "distribucion_secciones.png", dpi=150)
plt.show()