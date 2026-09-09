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

# Los agradecimientos no aportan nada en el contexto de la tesis.
# Quitamos las conclusiones generales porque ya están en inglés y es repetir información.
# Las referencias las tratamos de forma distinta señalándolas en función de los números a los que
# se apuntan en las secciones. Ej [42] ref 42
RUTAS_EXCLUIDAS = {
    "Agradecimientos",
    "Chapter 8: Conclusiones Generales",
    "References",
}
# Para evitar acabar con un último chunk muy pequeño que no nos permita guardar información útil
MINIMO_CHUNK = 300
# Función que nos divide el texto en sus frases. Divide si encuentra uno de estos caracteres .!? y lo  siguiente es
# uno o más espacios en blanco (space, tab...). (?<= esta parte es el lockbehind, es decir, lo que hace que cada vez que
# se encuentre un espacio en blanco, se pregunte si antes hay un . ! o una ?.
def dividir_en_frases(texto):
    return re.split(r"(?<=[.!?])\s+", texto)

# Cogemos los
def trocear(texto, tamano=TAMANO, solape=SOLAPE):
    if len(texto) <= tamano:
        return [texto]

    frases = dividir_en_frases(texto)
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

        texto = " ".join(s["parrafos"])

        # Nos saltamos los textos enteros de secciones si estos tienen menos de 100 caracteres, acabarían importando ruido
        # y no información
        if len(texto) < MINIMO:
            continue

        # Juntamos la ruta completa en un solo string
        ruta = " > ".join(s["ruta"])

        # Creamos una lista de diccionarios para cada chunk
        for i, trozo in enumerate(trocear(texto)):
            chunks.append({
                "id": f"{len(chunks):04d}", # Len de los chunks con números enteros de 4 díjitos (rellena con 0 delante si necesario
                "ruta": s["ruta"],
                "seccion": ruta,
                "parte": i + 1,                # Para tenerlas enumeradas
                "texto": f"{ruta}\n\n{trozo}", # Texto completo incluyendo ruta
                "texto_limpio": trozo,
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