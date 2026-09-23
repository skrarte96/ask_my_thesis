# Convierte el archivo word en formato Markdown
from pathlib import Path  # Rutas con Python
import re                 # Regular expressions
import shutil             # Para buscar, mover o copiar ejecutables
import subprocess         # Ejecuta otros programas para Python, con él llamamos a pandoc
import zipfile            # Leer y escribir archivos .ZIP, los .word son .ZIP
from PIL import Image     # Librería de imágenes de Python

# Rutas: RAIZ del proyecto, donde tenemoes el DOCX, donde guardaremos el .md creado a partir del .docx y MEDIA, donde
# guardaremos las imágenes de la tesis
RAIZ = Path(__file__).resolve().parent.parent
DOCX = RAIZ / "data" / "raw" / "electronic_and_optical_properties_of_organic_molecules_at_metal_surfaces_studied_by_scanning_tunneling_microscopy.docx"
SALIDA = RAIZ / "data" / "processed" / "tesis.md"
MEDIA = RAIZ / "data" / "processed" / "media" / "media"
# Regular expression para encontrar las imágenes .svg
RE_SVG = re.compile(r"image(\d+)\.svg")
# Capturamos toda la línea de la imagen: antes de la ruta, ruta y paréntesis de cierre
RE_IMG_MD = re.compile(r"(!\[[^\]]*\]\()([^)]+)(\))")

ANCHO_MAX = 1400
CALIDAD = 85        # Más del 85% no ganamos tanto solo mucho peso de imagen
# Metemos el fondo a la imagen, cambiamos a RGBA si tiene transparencia y a RGB si no
def aplanar(img):
    # Si tiene transparencia
    if img.mode in ("RGBA", "LA", "P"):                 # Checkeamos todas las imágenes que con modos de transparencia
        img = img.convert("RGBA")                       # Las pasamos todas a RGBA
        fondo = Image.new("RGB", img.size, "white")     # Creamos lienzo blanco del mismo tamaño que imagen
        fondo.paste(img, mask=img.split()[-1])          # Pegamos imagen usando máscara. Usamos canal alpha
        return fondo                                    # Donde imagen es opaca se pega, donde es transparente blanco
    return img.convert("RGB")                           # Devuelve imagen en RGB si no tenía transparencia
                                                        # Lo que admite JPEG

# Redimensionamos la imagen
def redimensionar(img, ancho_max=ANCHO_MAX):
    # Si ya es pequeña la dejamos tal cual
    if img.width <= ancho_max:
        return img
    # Factor de conversión para sacar la altura de la imagen a partir del ancho máximo que queremos
    alto = round(img.height * ancho_max / img.width)
    # Image.LANCZOS es el remuestreo (darle el color a la imagen) Lento pero tenemos pocas imágenes y da mejor calidad
    return img.resize((ancho_max, alto), Image.LANCZOS)

# Aplanamos, redimensionamos y guardamos las imágenes y calculamos bytes antes y despúes para saber cuanto peso
# hemos quitado
def comprimir_imagenes(origen, destino):
    # Le mete la ruta si no está ya
    destino.mkdir(parents=True, exist_ok=True)

    antes = 0       # Suma de bytes de imágenes originales
    despues = 0     # Suma de bytes de imágenes comprimidas
    n = 0           # Numero de imágenes

    # Buscamos todo lo que haya en la carpeta de origen
    for archivo in sorted(origen.glob("*")):
        # Quitamos todo lo que no sea .png .jpg o .jpeg
        if archivo.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        # Ruta de salida del archivo y pasado a formato .jpg (con .stem quitamos la extension y carpetas, solo nombre
        # del archivo)
        salida = destino / (archivo.stem + ".jpg")

        # Con las imágenes que queremos las aplanamos y redimensionamos y guardamos en la ruta de salida
        with Image.open(archivo) as img:
            img = aplanar(img)
            img = redimensionar(img)
            img.save(salida, "JPEG", quality=CALIDAD, optimize=True)

        # Sumamos bytes de la original, la redimensionada y que hemos procesado una imagen más
        antes += archivo.stat().st_size
        despues += salida.stat().st_size
        n += 1

    return n, antes, despues

def redirigir_a_comprimidas(md, carpeta_nueva):
    # Cambiamos la ruta de la imagen a la nueva (data/media)
    def cambiar(m):
        # Sacamos el nombre de la imagen
        nombre = Path(m.group(2)).stem + ".jpg"
        # devolvemos la nueva ruta
        return f"{m.group(1)}{carpeta_nueva}/{nombre}{m.group(3)}"

    # Leemos la línea del md
    texto = md.read_text(encoding="utf-8")
    # Si coincide con nuestra re para una imagen hacemos los cambios de ruta
    texto = RE_IMG_MD.sub(cambiar, texto)
    # La sobreescribimos en el md
    md.write_text(texto, encoding="utf-8")

# Comprobamos si tenemos pandoc, si no, hay que instalarlo
def comprobar_pandoc():
    if shutil.which("pandoc") is None:
        raise SystemExit(
            "No encuentro pandoc. Instálalo con: brew install pandoc"
        )

# Crea el comando que convierte el .docx a .md
def convertir(docx, salida, media):
    # Crea las carpetas necesarias si no están ya en la ruta de salida
    salida.parent.mkdir(parents=True, exist_ok=True)

    # Crea el comando a convertir el .word
    comando = [
        "pandoc",
        str(docx),
        "-o", str(salida),
        "--to=markdown",
        "--wrap=none",
        f"--extract-media={media.parent.relative_to(RAIZ)}",
    ]

    # Ejecuta el comando
    subprocess.run(comando, check=True, cwd=RAIZ)

# Extraemos las imágenes del archivo .word, aprovechando que se comporta básicamente como un .ZIP y las guardamos en
# la carpeta media
def extraer_imagenes(docx, destino):
    destino.mkdir(parents=True, exist_ok=True)

    # Abrimos el .word como formato zip (que es lo que es al final)
    with zipfile.ZipFile(docx) as z:
        # Aprovecha con el startwith que word guarda las imágenes en una carpeta word/media, para sacar todas las
        # imágenes del word de ahí y guardar sus nombres
        nombres = [n for n in z.namelist() if n.startswith("word/media/")]


        for nombre in nombres:
            # Tomamos solo el nombre de la imagen y le pegamos antes la ruta de destino donde queremos guardarla
            archivo = destino / Path(nombre).name
            # Abrimos la imagen del archivo de word z.open... y luego de , creamos documento donde guardar la imagen
            # "wb" en binario para cargar bien la imagen
            with z.open(nombre) as origen, open(archivo, "wb") as f:
                # copia la imagen por trozos sin cargar archivo entero en memoria para no saturarlo
                shutil.copyfileobj(origen, f)

    # Devuelve el número de imágenes extraídas del zip de word
    return len(nombres)

# Va a redirigir las imágenes .png donde antes iban las .svg en el texto
def redirigir_svg(md, carpeta):
    # Microfunción metida aquí porque solo la queremos para señalar al .png gemelo del .svg
    def png_gemelo(coincidencia):
        # Cogemos el número de imagen .svg
        numero = int(coincidencia.group(1))
        # Creamos el candidato al que pertenece su .png. Si hay imagen3.svg, su gemela debe ser imagen2.png
        candidato = carpeta / f"image{numero - 1}.png"

        # Si ese candidato existe, sustituimos el .svg por su gemelo .png
        if candidato.exists():
            return f"image{numero - 1}.png"

        return coincidencia.group(0)

    # Leemos todo el .md
    texto = md.read_text(encoding="utf-8")

    # Buscamos con la regular expression donde van las .svg. En verdad, el número de .svg
    antes = len(RE_SVG.findall(texto))
    # Cambiamos las .svg por su gemela .png
    texto = RE_SVG.sub(png_gemelo, texto)
    # Número de .svg que quedan sin gemelo
    despues = len(RE_SVG.findall(texto))

    md.write_text(texto, encoding="utf-8")

    # Devolvemos las imágenes redirigidas, las que quedaron sin gemelo (.svg que no podemos cambiar a .png)
    return antes - despues, despues

# Borramos las imágenes en formato .svg de la carpeta MEDIA
def borrar_svg(carpeta):
    # Crea un generador con los nombres de las imágenes .svg (.glob) solo podemos recorrer la lista una vez
    svgs = list(carpeta.glob("*.svg"))

    # para cada imagen de la lista creada borramos ese nombre
    for s in svgs:
        s.unlink()
    # Devuelve número de imágenes borradas
    return len(svgs)


if __name__ == "__main__":
    # Checkeamos que tengamos pandoc
    comprobar_pandoc()

    # Checheamos que tengamos la tesis o el .docx correspondiente
    if not DOCX.exists():
        raise SystemExit(f"No encuentro la tesis en {DOCX}")

    # Convertimos el .docx a pandoc
    print("Convirtiendo con pandoc (tarda un poco)...")
    convertir(DOCX, SALIDA, MEDIA)

    # Sacamos número de imágenes extraídas
    extraidas = extraer_imagenes(DOCX, MEDIA)
    # Número .svg cambiadas y las que no tenían gemelo
    redirigidas, sin_gemelo = redirigir_svg(SALIDA, MEDIA)
    # Número de .svg borradas
    borrados = borrar_svg(MEDIA)

    # Número de líneas que tiene el archivo .md creado
    lineas = len(SALIDA.read_text(encoding="utf-8").splitlines())

    # Info a desplegar a modo de comprobación
    print(f"\nLíneas en el markdown: {lineas:,}")
    print(f"Imágenes extraídas del .docx: {extraidas}")
    print(f"Referencias SVG redirigidas a PNG: {redirigidas}")
    print(f"Referencias SVG sin gemelo: {sin_gemelo}")
    print(f"Archivos SVG borrados: {borrados}")
    print(f"\nGuardado en: {SALIDA}")

    # Procesado de imágenes, aplanado y redimensionado
    MEDIA_FINAL = RAIZ / "data" / "media"

    n_img, antes, despues = comprimir_imagenes(MEDIA, MEDIA_FINAL)
    redirigir_a_comprimidas(SALIDA, "data/media")

    print(f"\nImágenes comprimidas: {n_img}")
    print(f"  {antes / 1024 / 1024:.1f} MB → {despues / 1024 / 1024:.1f} MB")