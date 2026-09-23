# Librerias para las rutas y para el archivo .json creado de la tesis
from pathlib import Path
import json
# Importamos re para usar las regular expressions
import re

# Ruta con la raiz del proyecto, ruta de entrada de datos, el .json hecho de la tesis y ruta de salida, el .json
# dividido con los chunks
RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "data" / "processed" / "secciones.json"
SALIDA = RAIZ / "data" / "processed" / "chunks.json"

# Tamaño de los chunks, solape entre ellos, mínima longitud de caracteres para no ser eliminada esa sección.
# Las unidades son caracteres.
TAMANO = 1000
SOLAPE = 150
MINIMO = 100

# Quitamos los asteriscos en las abreviaturas para que se puedan vectorizar bien y no como ruido
RE_ENFASIS = re.compile(r"[*_]{1,3}(?=\S)|(?<=\S)[*_]{1,3}")

# Los agradecimientos no aportan nada en el contexto de la tesis.
# Quitamos las conclusiones generales porque ya están en inglés y es repetir información.
# Las referencias las tratamos de forma distinta señalándolas en función de los números a los que
# se apuntan en las secciones. Ej [42] ref 42
RUTAS_EXCLUIDAS = {
    "Resumen",
    "Agradecimientos",
    "Chapter 8: Conclusiones Generales",
    "References",
}
# Para evitar acabar con un último chunk muy pequeño que no nos permita guardar información útil
MINIMO_CHUNK = 300
# Función que nos divide el texto en sus frases. Divide si encuentra uno de estos caracteres .!? y lo  siguiente es
# uno o más espacios en blanco (space, tab...). (?<= esta parte es el lockbehind, es decir, lo que hace que cada vez que
# se encuentre un espacio en blanco, se pregunte si antes hay un . ! o una ?. A parte, en caso de que tengamos párrafos
# indivisibles como es el caso de una ecuación o un pie de página, lo trata como texto indivisible y lo adjunta tal cual
def dividir_en_frases(texto):
    unidades = []

    # Checkeamos cada línea
    for linea in texto.split("\n"):
        # Sacamos los espacios delante y atrás que word nos haya podido meter
        linea = linea.strip()

        # En caso de que no haya línea pasamos a la siguiente línea del bucle for
        if not linea:
            continue

        # Dividimos por frases si es que se puede dividir
        partes = re.split(r"(?<=[.!?])\s+", linea)

        # En caso de que no se pueda dividir (pie de página o ecuación) la adjuntamos entera (la línea)
        if len(partes) == 1:
            unidades.append(linea)
        else:
            # Si se pudo dividir, adjuntamos la línea separada por sus frases
            unidades.extend(partes)

    # Devuelve las unidades, frases separadas, ecuaciones y pies de página siempre juntos
    return unidades

# Es una salvaguarda. Se activa en el caso de que una unidad sea más larga que un chunk entero. (que el TAMANO elegido)
# Usamos esta función porque si la unidad es más larga que un chunk entero perdemos el significado de TAMANO y habrá
# secciones con tamaño mayor que TAMANO.
def partir_duro(frase, tamano, solape):
    # Guardamos los trozos aquí
    trozos = []
    inicio = 0

    # Mantenemos el bucle mientras nuestro contador (inicio) no haya llegado al final (len(frase).
    # No tenemos buckle infinito porque inicio siempre crece en cada iteración
    while inicio < len(frase):
        # Final tentativo
        fin = inicio + tamano

        # Si fin fuese mayor que la longitud de la frase no tenemos donde cortar porque debe meterse entera para no
        # perder su significado (la frase). Si fuese menor, tenemos que ver co´´o la rellenamos, en ese caso usamos
        # .rfind
        if fin < len(frase):
            # Encuentra entre la longitud inicio y fin el último espacio, partimos entre palabras y no partimos ninguna
            # palabra a la mitad. si no encuentra un espacio válido. rfind nos devuelve -1. rfind empieza a contar desde
            # la derecha (desde el final)
            hueco = frase.rfind(" ", inicio, fin)
            # Si encontró un hueco válido y no un -1 de que no hay, movemos fin al hueco
            if hueco > inicio:
                fin = hueco

        # Añade a la lista de trozos la frase partida por [inicio - fin]
        trozos.append(frase[inicio:fin].strip())
        # Elegimos el máximo de estos dos tramos, en caso de qu el corte posible (fin - solape) sea menor que el primer
        # inicio acabaríamos con un bucle infinito, cogemos entonces inicip +1 y nos aseguramos que inicio siempre va
        # en aumento
        inicio = max(fin - solape, inicio + 1)

    # Devuelve los trozos
    return trozos
def trocear(texto, tamano=TAMANO, solape=SOLAPE):
    if len(texto) <= tamano:
        return [texto]

    # Colocamos aquí la división de frases y el partir duro en el caso de que sea necesario porque hemos encontrado una
    # frase que se pasa de tamaño de chunk
    frases = []
    # para cada frase en las frases divididas
    for f in dividir_en_frases(texto):
        # si la longitud de tamaño excede la del chunk deseado (TAMANO), la partimos sin piedad
        if len(f) > tamano:
            frases.extend(partir_duro(f, tamano, solape))
        # si no es necesario la adjuntamos a nuestras frases tranquilamente
        else:
            frases.append(f)
    trozos = []
    actual = ""
    # Juntamos frases hasta que tengan el tamaño especificado en TAMANO
    for frase in frases:
        # Para ir pegando las frases cuando son demasiado pequeñas
        if len(actual) + len(frase) + 1 <= tamano:
            actual = f"{actual} {frase}".strip()
        else:
            # Si actual no está vacío
            if actual:
                # Formamos el primer trozo (chunk)
                trozos.append(actual)
            # Si actual está vacío se queda vacío, si no lo está coge el solape y lo junta con la frase
            cola = actual[-solape:] if actual else ""
            actual = f"{cola} {frase}".strip()
    # Si actual no está vacío cuando acabe el bucle añade a trozos el último solape y la última frase
    if actual:
        # Si trozos no está vacía y la len(actual) es menor que el número de caracteres mínimo puesto para un chunk
        # añadimos el actual pequeño final a el último trozo de la lista
        if trozos and len(actual) < MINIMO_CHUNK:
            trozos[-1] = f"{trozos[-1]} {actual}".strip()
        else:
            # En caso de que actual sea mayor que MINIMO_CHUNK lo adjuntamos como trozo final y ya
            trozos.append(actual)

    return trozos


def construir_chunks(secciones):
    chunks = []
    # Excluimos las rutas arriba mencionadas que no nos aportan información extra
    for s in secciones:
        if s["ruta"][0] in RUTAS_EXCLUIDAS:
            continue

        # Une las líneas de texto con separadores de línea
        texto = "\n".join(s["parrafos"])

        # Quitamos los asteriscos de las abreviaturas
        texto = RE_ENFASIS.sub("", texto)

        # Nos saltamos los textos enteros de secciones si estos tienen menos de 100 caracteres, acabarían importando ruido
        # y no información
        if len(texto) < MINIMO:
            continue

        # Juntamos la ruta completa en un solo string
        ruta = " > ".join(s["ruta"])

        # Creamos una lista de diccionarios para cada chunk
        for i, trozo in enumerate(trocear(texto)):
            chunks.append({
                "id": f"{len(chunks):04d}",
                # Len de los chunks con números enteros de 4 dígitos (rellena con 0 delante si necesario)
                "ruta": s["ruta"],
                "seccion": ruta,
                "parte": i + 1,                     # Para tenerlas enumeradas
                "texto": f"{ruta}\n\n{trozo}",      # Texto completo incluyendo ruta
                "texto_limpio": trozo,
                "imagenes": s.get("imagenes", []),  # Metemos las imágenes
                "n": len(trozo),
            })

    return chunks

# Solo se ejecuta si corremos el programa directamente desde su propio script (aquí)
if __name__ == "__main__":
    # Leemos el archivo de secciones
    with open(ENTRADA, "r", encoding="utf-8") as f:
        secciones = json.load(f)
    # Creamos los chunks
    chunks = construir_chunks(secciones)

    # Escribimos el nuevo archivo con los chunks
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    # Prueba, info sobre los chunks generados y visualización del sexto chunk como ejemplo
    tamanos = [c["n"] for c in chunks]
    print(f"Chunks generados: {len(chunks)}")
    print(f"Tamaño medio: {sum(tamanos) // len(tamanos)}")
    print(f"Mínimo: {min(tamanos)}  Máximo: {max(tamanos)}")
    print(f"\nEjemplo:\n")
    print(chunks[5]["texto"][:400])