# Coge todas nuestras secciones divididas y lo que hace es crear los chunks
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
# Las unidades son caracteres y mínimo tamaño de chunk que deberíamos tener,
# para evitar acabar con un último chunk muy pequeño que no nos permita guardar información útil
TAMANO = 1000
MINIMO = 100
MINIMO_CHUNK = 300

# Carácter que no existe en la tesis: lo usamos como marcador temporal para las fórmulas
MARCA = "\x00"

# Número de frases que vamos a meter de solape (evitamos cortar por caracteres para no perder significados
# y romper fórmulas
FRASES_SOLAPE = 2

# Fórmulas completas, de bloque o de línea. re.DOTALL porque una fórmula de
# bloque puede ocupar varias líneas y necesitamos cogerla entera.
RE_FORMULA = re.compile(r"\$\$.+?\$\$|\$[^$\n]+?\$", re.DOTALL)

# Quitamos las negritas en markdown que rompen las abreviaturas para que se puedan vectorizar bien y no como ruido
# Esperanza de que el programa las entienda y las ponga cuando alguien pregunte por las abreviaturas
RE_NEGRITA = re.compile(r"[*]{2,3}(?=\S)|(?<=\S)[*]{2,3}")

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
# Mete el marcador en las fórmulas de forma que cada una esté numerada con los caracteres de MARCA que sabemos
# con seguridad que no están en el texto de la tesis
def proteger_formulas(texto):
    # Guardamos las fórmulas aquí
    formulas = []

    # Colocamos las marcas
    def guardar(m):
        formulas.append(m.group(0))
        return f"{MARCA}{len(formulas) - 1}{MARCA}"

    # Devolvemos la fórmula marcada y su texto de fórmula
    return RE_FORMULA.sub(guardar, texto), formulas

# Esta función restaura la fórmula después del procesado de los trozos texto
def restaurar_formulas(texto, formulas):

    return re.sub(
        rf"{MARCA}(\d+){MARCA}",                # Capturamos número de fórmula
        lambda m: formulas[int(m.group(1))],    # Cogemos ese número
        texto,                                  # Sustituimos número por fórmula (igual al índice en formulas)
    )

# Función que nos divide el texto en sus frases. Divide si encuentra uno de estos caracteres .!? y lo  siguiente es
# uno o más espacios en blanco (space, tab...) (?<= esta parte es el lock-behind, es decir, lo que hace que cada vez que
# se encuentre un espacio en blanco, se pregunte si antes hay un . ! o una ?. A parte, en caso de que tengamos párrafos
# indivisibles como es el caso de una ecuación o un pie de página, lo trata como texto indivisible y lo adjunta tal cual
# Las fórmulas están protegidas antes de ser separadas de forma que no aparezcan rotas en los chunks luego
def dividir_en_frases(texto):
    # antes de hacer nada protegemos las fórmulas
    texto, formulas = proteger_formulas(texto)

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
    # Vuelve a colocar las fórmulas
    return [restaurar_formulas(u, formulas) for u in unidades]

def trocear(texto, tamano=TAMANO, frases_solape=FRASES_SOLAPE):
    # Dividimos el texto en frases
    unidades = dividir_en_frases(texto)
    # Si no tenemos nada que dividir devolvemos una lista vacía
    if not unidades:
        return []

    # Donde irán los trozos y en actual, la lista de chunks que iremos montando
    trozos = []
    actual = []

    # Vamos frase por frase de la tesis
    for unidad in unidades:

        # Número de caracteres que ocupa el chunk +1 de los espacios entre frases
        ocupado = sum(len(u) + 1 for u in actual)

        # Si al meter esta frase nos pasamos, cerramos el chunk
        if actual and ocupado + len(unidad) > tamano:
            trozos.append(" ".join(actual))

            # El siguiente chunk arranca repitiendo las últimas frases del anterior
            cola = actual[-frases_solape:]

            # Si no caben porque el solape ocupa la mitad de tamaño del chunk,
            # vamos soltando la frase más antigua hasta que quepa.
            # Así nos quedamos sin solape solo cuando ni una sola frase cabe,
            # que es el caso de una fórmula de bloque enorme
            while cola and sum(len(u) + 1 for u in cola) > tamano // 2:
                cola = cola[1:]
            # Aquí metemos lo que quede de la cola
            actual = cola

        # Metemos la siguiente frase en actual (el chunk a montar)
        actual.append(unidad)
    # Si queda un último cúmulo de frases en actual
    if actual:
        # Lo metemos todo en la variable último
        ultimo = " ".join(actual)
        # Si tenemos trozos hechos y ese último es menor que el mínimo puesto, lo adjuntamos al último trozo
        # Mejor que nos quede un trozo grande a uno pequeño
        if trozos and len(ultimo) < MINIMO_CHUNK:
            trozos[-1] = f"{trozos[-1]} {ultimo}".strip()
        else:
            trozos.append(ultimo)

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
        texto = RE_NEGRITA.sub("", texto)

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