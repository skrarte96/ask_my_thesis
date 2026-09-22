# Sencillo programa de seguimiento para detectar cuantas ecuaciones deberían ser corregidas
# Librerias de rutas y regular expressions
from pathlib import Path
import re

# Rutas para encontrar la tesis limpia en .MD
RAIZ = Path(__file__).resolve().parent.parent
MD = RAIZ / "data" / "processed" / "tesis_limpia.md"

# Regular expression para sacar las ecuaciones mal puestas en el .word
RE_INLINE = re.compile(r"(?<![\\$])\$(?!\$)([^$\n]+?)(?<!\\)\$(?!\$)")

# Leemos la tesis_limpia.md
texto = MD.read_text(encoding="utf-8")

problemas = []
# Vamos línea por línea detectando si la regular expression se cumple
for n, linea in enumerate(texto.splitlines(), 1):
    for m in RE_INLINE.finditer(linea):
        dentro = m.group(1)
        balance = dentro.count("(") - dentro.count(")")
        if balance != 0:
            despues = linea[m.end():m.end() + 3]
            problemas.append((n, balance, dentro, despues))

print(f"Fórmulas en línea con paréntesis desequilibrados: {len(problemas)}\n")
for n, balance, dentro, despues in problemas[:25]:
    print(f"línea {n:>5}  balance {balance:+d}  ${dentro[:60]}$  →  sigue: '{despues}'")