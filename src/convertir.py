# Convierte el archivo word en formato Markdown
from pathlib import Path  # Rutas con Python
import re                 # Regular expressions
import shutil             # Para buscar, mover o copiar ejecutables
import subprocess         # Ejecuta otros programas para Python, con él llamamos a pandoc
import zipfile            # Leer y escribir archivos .ZIP, los .word son .ZIP

# Rutas: RAIZ del proyecto, donde tenemoes el DOCX, donde guardaremos el .md creado a partir del .docx y MEDIA, donde
# guardaremos las imágenes de la tesis
RAIZ = Path(__file__).resolve().parent.parent
DOCX = RAIZ / "data" / "raw" / "electronic_and_optical_properties_of_organic_molecules_at_metal_surfaces_studied_by_scanning_tunneling_microscopy.docx"
SALIDA = RAIZ / "data" / "processed" / "tesis.md"
MEDIA = RAIZ / "data" / "processed" / "media" / "media"
# Regular expression para encontrar las imágenes .svg
RE_SVG = re.compile(r"image(\d+)\.svg")

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