> Documentación en español. El código y los comentarios técnicos siguen las
> convenciones habituales en inglés cuando corresponde.

# Ask My Thesis

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22911361.svg)](https://doi.org/10.5281/zenodo.22911361)

Sistema de preguntas y respuestas (RAG) sobre mi tesis doctoral en física, sobre
microscopía de efecto túnel (STM) y plasmónica. Se le hace una pregunta en lenguaje
natural, el sistema busca los fragmentos relevantes del documento y un modelo de
lenguaje redacta la respuesta indicando de qué secciones procede.

El objetivo es que responda únicamente con el contenido de la tesis y que diga
explícitamente cuándo la información no está en ella, en lugar de inventarla.

**Estado: en desarrollo.** El pipeline completo funciona desde la terminal. Queda la
evaluación sistemática y la interfaz web.

---

## Cómo funciona

```
tesis.docx  (251 MB, 158 páginas)
    │
    ├── convertir.py ............ pandoc: .docx → Markdown
    │                              ecuaciones a LaTeX, tablas, imágenes
    │
    ├── arreglar_encabezados.py .. repara la jerarquía usando python-docx
    │                              como fuente de referencia
    │
    ├── ingest.py ............... Markdown → 76 secciones con ruta jerárquica
    │
    ├── chunk.py ................ 388 fragmentos de ~880 caracteres
    │                              con solapamiento de 150
    │
    ├── embed.py ................ 388 vectores de 768 dimensiones
    │                              (modelo multilingüe, ejecutado en local)
    │
    ├── retrieve.py ............. similitud coseno → los 5 fragmentos más cercanos
    │
    └── generate.py ............. LLM redacta la respuesta con citas de sección
```

Cada paso escribe un archivo intermedio, de forma que se puede sustituir una pieza sin
tocar las demás. Eso permitió, por ejemplo, cambiar por completo el método de
extracción sin rehacer el chunking ni los embeddings.

---

## Stack

| Componente | Herramienta | Coste |
|---|---|---|
| Conversión del documento | pandoc | 0 € |
| Estructura del documento | python-docx | 0 € |
| Embeddings | `intfloat/multilingual-e5-base` (local) | 0 € |
| Búsqueda vectorial | numpy | 0 € |
| Generación | Ollama + `qwen2.5:7b` / `qwen2.5:14b` (local) | 0 € |
| Interfaz *(pendiente)* | Streamlit | 0 € |

Todo el pipeline corre en local sin coste. En el despliegue público está previsto el
patrón **BYOK** (*Bring Your Own Key*): cada visitante introduce su propia clave de
API para la parte de generación, de forma que nadie paga el consumo de otros.

---

## Requisitos previos

- Python 3.12
- [pandoc](https://pandoc.org) — `brew install pandoc` en macOS
- [Ollama](https://ollama.com) — `brew install ollama`, y después
  `ollama pull qwen2.5:7b`

## Uso

1. Descarga la tesis en formato .docx desde
   [Zenodo](https://doi.org/10.5281/zenodo.22911361) y colócala en `data/raw/`.

2. Instala las dependencias:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

3. Ejecuta el pipeline (cada paso depende del anterior):

```bash
python -m src.convertir              # .docx → markdown, imágenes extraídas y comprimidas
python -m src.arreglar_encabezados   # → tesis_limpia.md
python -m src.ingest                 # → secciones.json
python -m src.chunk                  # → chunks.json
python -m src.embed                  # → embeddings.npy
```

4. Con `ollama serve` corriendo en otra terminal:

```bash
python -m src.generate               # preguntas y respuestas interactivas
```

También se puede consultar solo el buscador, sin generación:

```bash
python -m src.retrieve
```

---

## Estructura del proyecto

```
ask-my-thesis/
├── data/
│   ├── raw/                  # tesis original (no versionada: 251 MB)
│   ├── processed/            # archivos intermedios (no versionados)
│   └── preguntas.json        # set de evaluación (41 preguntas)
├── src/
│   ├── convertir.py          # .docx → Markdown con pandoc
│   ├── arreglar_encabezados.py
│   ├── ingest.py             # Markdown → secciones estructuradas
│   ├── chunk.py              # secciones → fragmentos
│   ├── embed.py              # fragmentos → vectores
│   ├── retrieve.py           # búsqueda por similitud
│   ├── generate.py           # generación de respuestas
│   └── evaluar_retrieval.py  # métricas de recuperación
├── notebooks/                # scripts de exploración y gráficas
├── requirements.txt
├── LICENSE
└── README.md
```

En `data/processed/` no se versiona nada porque todo se regenera ejecutando el
pipeline. La regla aplicada: **en el repositorio va lo que no se puede reconstruir**.

---

## Decisiones técnicas

### Por qué RAG y no fine-tuning

Ajustar un modelo con el texto de la tesis sería caro, lento y produciría respuestas
no verificables. RAG permite citar la sección exacta de la que procede cada
afirmación, que es justo lo que se necesita para consultar un documento académico.

### Por qué pandoc en lugar de solo python-docx

La primera versión usaba `python-docx`, que lee bien la estructura de estilos pero
**descarta silenciosamente las ecuaciones**: donde había una fórmula quedaba un hueco
vacío, dejando frases sin sujeto en todo el formalismo teórico.

pandoc convierte las ecuaciones de Word a LaTeX, y de paso recupera las 35 tablas y
los pies de figura. El texto útil pasó de 292.209 a 337.886 caracteres, y las
secciones con ecuaciones de 0 a 40.

Como contrapartida, pandoc no reconoció 5 de los 82 encabezados del documento e
importó las cabeceras de página al cuerpo del texto, partiendo frases por la mitad.
Por eso `arreglar_encabezados.py` usa python-docx como fuente de referencia de la
estructura para parchear la salida de pandoc: **cada herramienta para lo que acierta**.

### Imágenes: SVG y sus gemelos PNG

81 de las 95 figuras estaban guardadas como SVG, que se visualizaban con pérdidas de
contenido. Word guarda junto a cada SVG una copia PNG de respaldo, así que el script
extrae esos PNG del ZIP y reescribe las referencias del Markdown. 81 de 81 redirigidas
correctamente.

### Chunking

Tamaño objetivo de 1.000 caracteres con 150 de solapamiento. Tres refinamientos sobre
el corte por posición:

- **Corte por frases**, no por número de caracteres, para no partir ideas a la mitad.
- **Unidades indivisibles**: una línea sin puntuación de frase (una ecuación, una fila
  de tabla, un pie de figura) se trata como un bloque que nunca se parte. Son 298 de
  las 820 líneas del documento.
- **Fusión de huérfanos**: un resto final de menos de 300 caracteres se une al
  fragmento anterior en vez de quedar suelto sin contexto.

Cada fragmento lleva delante su ruta jerárquica completa
(`Chapter 4 > 4.3 Electronic Structure > 4.3.1 C90 on Au(111)`) **dentro del texto que
se vectoriza**. Esto resuelve el problema de las secciones con títulos idénticos:
`4.2.1 C90 on Au(111)` y `4.3.1 C90 on Au(111)` hablan de cosas distintas, y la ruta
las separa en el espacio de embeddings.

Distribución resultante: media 876 caracteres, mínimo 302, máximo 1.277.

### Modelo de embeddings multilingüe

La tesis está en inglés y las preguntas pueden ser en español. Un modelo monolingüe
situaría "corriente túnel" y "tunnelling current" en puntos alejados del espacio
vectorial y el sistema no encontraría nada. `multilingual-e5-base` los alinea.

Los vectores se normalizan a longitud 1, de forma que la similitud coseno se reduce a
un producto escalar y la búsqueda sobre los 388 fragmentos es una única multiplicación
matriz-vector.

### Secciones excluidas del índice

`Agradecimientos`, `Resumen`, `Chapter 8: Conclusiones Generales` y `References`.

El caso interesante es el **Resumen**: al ser un texto que menciona todos los temas de
la tesis sin profundizar en ninguno, su vector quedaba en una posición central del
espacio semántico y aparecía entre los resultados de casi cualquier pregunta,
desplazando a las secciones que sí contenían la respuesta.

### Capa de abstracción entre backends

`generate.py` expone una función `generar_respuesta(pregunta, fragmentos, backend)`
y un registro de backends disponibles. El resto del código no sabe si por debajo se
está hablando con Ollama en `localhost` o con una API remota.

Esto no es un ejercicio de estilo: el modelo local no cabe en la memoria del servidor
donde se desplegará la aplicación, así que el sistema tiene que poder usar los dos
sin cambiar nada más.

---

## Evaluación

Set de **41 preguntas** en `data/preguntas.json`, escritas conociendo el contenido de
la tesis, con la sección donde está cada respuesta anotada a mano:

| Tipo | Nº | Qué mide |
|---|---|---|
| factual | 13 | recuperación y redacción básicas |
| comparativa | 6 | recuperar información de dos secciones distintas |
| numerica | 6 | alucinación de datos concretos |
| general | 6 | límites del RAG con preguntas de alcance amplio |
| formula | 5 | uso correcto del LaTeX recuperado |
| trampa | 5 | abstención honesta |

Las preguntas trampa no son absurdos evidentes, sino **cercanas pero falsas**: C90
sobre KBr en lugar de NaCl, conclusiones sobre C60 en lugar de C90, la ecuación de
Schrödinger en 2D. Son las que de verdad distinguen un sistema honesto de uno que
complace al usuario.

Métricas previstas: *recall@5* (global y por tipo), posición del primer acierto,
tasa de abstención correcta, y comparación entre `qwen2.5:7b` y `qwen2.5:14b` con el
mismo contexto recuperado.

---

## Limitaciones conocidas

- **El umbral de similitud no discrimina bien.** Una pregunta legítima puntúa 0,81 y
  una pregunta absurda 0,76: el margen es demasiado estrecho para decidir con un
  número. La abstención se delega en el modelo mediante instrucciones explícitas.

- **Redundancia en la recuperación.** Con frecuencia los 5 fragmentos recuperados
  pertenecen a la misma sección, desaprovechando contexto que podría cubrir el tema
  desde varios ángulos. Una técnica de diversificación (MMR) lo mitigaría.

- **Los modelos de 7B no sostienen muchas reglas a la vez.** Al ajustar el prompt,
  arreglar un comportamiento tiende a romper otro (idioma, formato de citas,
  traducción de siglas). Es la razón principal para comparar con un modelo mayor.

- **Las referencias bibliográficas están desconectadas.** El texto contiene `[42]` y
  la bibliografía contiene la entrada 42, pero nada las enlaza. Es resoluble con una
  búsqueda en diccionario, no con RAG.

- **Preguntas de alcance amplio.** "¿De qué trata la tesis?" requiere información
  repartida por todo el documento y el sistema solo dispone de 5 fragmentos. Es una
  limitación estructural del RAG básico, no un fallo de implementación.

- **Efecto de las ambigüedades en las preguntas**El recall@5 del 86% no es un techo del sistema sino un reflejo de la ambigüedad
inherente a las preguntas en lenguaje natural. "¿Qué significa HOMO?" admite dos
lecturas —el desarrollo de la sigla o el concepto físico— y el sistema resuelve la
segunda. Las técnicas que mitigan esto (reescritura de consultas, búsqueda híbrida,
memoria conversacional) quedan identificadas como trabajo futuro.
---

## Pendiente

- [ ] Evaluación del retrieval (métricas automáticas)
- [ ] Evaluación de la generación y comparación 7B vs 14B
- [ ] Ajuste de parámetros con datos: tamaño de fragmento, número de fragmentos
      recuperados, temperatura
- [ ] Interfaz con Streamlit
- [ ] Backends de API (Anthropic, Google) para el despliegue
- [ ] Despliegue público con BYOK
- [ ] Mostrar las figuras de la tesis junto a las respuestas
- [ ] *(opcional)* API propia con FastAPI
- [ ] *(opcional)* Enlazar las citas `[N]` con la bibliografía

---
## Recalls

Recall en función de k:

| k | Recall (alguna sección) | Recall (todas) | Posición media del 1er acierto |
|---|---|---|---|
| 3 | 83 % | 72 % | 1,3 |
| 5 | 86 % | 83 % | 1,4 |
| 10 | 92 % | 92 % | 1,7 |

Recall@5 por tipo de pregunta:

| Tipo | Recall@5 | Recall@10 |
|---|---|---|
| comparativa | 6/6 (100 %) | 6/6 (100 %) |
| formula | 5/5 (100 %) | 5/5 (100 %) |
| numerica | 5/6 (83 %) | 6/6 (100 %) |
| general | 5/6 (83 %) | 5/6 (83 %) |
| factual | 10/13 (77 %) | 11/13 (85 %) |

Calibración del umbral de similitud:

| Grupo | Similitud media | Mínimo | Máximo |
|---|---|---|---|
| Preguntas con respuesta en la tesis | 0,836 | 0,748 | — |
| Preguntas trampa | 0,833 | — | 0,877 |

Las dos distribuciones están superpuestas: la pregunta trampa con mayor similitud
(0,877) supera a cualquier pregunta legítima, y la más baja de estas (0,748) queda
por debajo de la media de las trampas. No existe ningún umbral que separe ambos
grupos, lo que descarta filtrar por similitud y obliga a delegar la abstención en
el modelo de lenguaje.

## Datos

El pipeline parte del documento original en formato .docx (251 MB), que no se
incluye en el repositorio por tamaño. Descárgalo desde Zenodo y colócalo en
`data/raw/`:

**https://doi.org/10.5281/zenodo.22911361**

La versión oficial de la tesis, en PDF, está depositada en
[Biblos-e Archive (UAM)](http://hdl.handle.net/10486/715334). El pipeline usa el
.docx porque conserva las ecuaciones en formato editable y la estructura de
secciones, que se pierden al extraer texto de un PDF.

## Licencia

El código de este proyecto se publica bajo licencia MIT.

La tesis es obra del autor y está depositada en Biblos-e Archive (UAM) y en
Zenodo bajo licencia CC BY-NC-ND 4.0: su reutilización requiere citar la fuente,
reconocer la autoría, no obtener beneficio comercial y no realizar obras derivadas.
