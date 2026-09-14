# Importamos para rutas y regular expressions
from pathlib import Path
import re

# Rutas: Raiz del proyecto, tesis en formato .md y carpeta media con las imágenes
RAIZ = Path(__file__).resolve().parent.parent
MARKDOWN = RAIZ / "data" / "processed" / "tesis.md"
MEDIA = RAIZ / "data" / "processed" / "media" / "media"

# Regular expression para coger todas las imágenes en formato .svg
PATRON = re.compile(r"image(\d+)\.svg")

# Llamaremos a esta función para que encuentre la imagen .png gemela de la imagen.svg (los .svg se me guardan mal)
def png_gemelo(coincidencia):
    # Devuelve lo que capturó el primer grupo de paréntesis, osea el dígito de la imagen, lo pasamos a int que group()
    # devuelve de normal un str
    numero = int(coincidencia.group(1))
    # Sacamos el path y la imagen con el gemelo de formato .png
    candidato = MEDIA / f"image{numero - 1}.png"

    # Por si acaso no existe su gemelo que no nos rompa el programa
    if candidato.exists():
        return f"image{numero - 1}.png"

    # .group(0) es la coincidencia completa todo el formato 'figure8.svg' por ejemplo.
    return coincidencia.group(0)

# Leemos el archivo de la tesis en mardown
texto = MARKDOWN.read_text(encoding="utf-8")

# Hace lista de todas las veces que encuentra una imagen .svg en la tesis.md
svg_antes = len(PATRON.findall(texto))

# Sustituye todas las coincidencias de .svg por su gemelo .png
texto_nuevo = PATRON.sub(png_gemelo, texto)

# Lo mismo que antes una vez aplicada las sustituciones de coincidencia, debería ser cero
svg_despues = len(PATRON.findall(texto_nuevo))

# Reescribe la tesis.md con las nuevas coincidencias, es decir, cambiando las imágenes .svg por las .png
MARKDOWN.write_text(texto_nuevo, encoding="utf-8")

# Vemos cómo han quedado.
print(f"Referencias SVG encontradas:  {svg_antes}")
print(f"Redirigidas a PNG:            {svg_antes - svg_despues}")
print(f"Sin gemelo (siguen en SVG):   {svg_despues}")