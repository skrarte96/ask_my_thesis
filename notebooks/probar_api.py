# notebooks/probar_api.py
import os
from src.embed import cargar_modelo
from src.retrieve import cargar_indice, buscar
from src.generate import generar_respuesta

# Cargamos tesis en formato chunks y sus vectores y el modelo
chunks, vectores = cargar_indice()
modelo = cargar_modelo()

# Pregunta a hacer
pregunta = "¿Qué es el efecto túnel cuántico?"
# Buscamos los chunks que mejor den respuesta
resultados = buscar(modelo, chunks, vectores, pregunta)

# Generamos la respuesta
texto = generar_respuesta(
    pregunta,
    resultados,
    backend="google",
    clave=os.environ["GOOGLE_API_KEY"],
)
# Printeamos la respuesta
print(texto)