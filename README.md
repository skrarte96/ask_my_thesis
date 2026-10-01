# Ask My Thesis

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22911361.svg)](https://doi.org/10.5281/zenodo.22911361)

Sistema de preguntas y respuestas (RAG) sobre mi tesis doctoral en física, sobre
microscopía de efecto túnel (STM) y plasmónica. Se le hace una pregunta en lenguaje
natural, el sistema busca los fragmentos relevantes del documento y un modelo de
lenguaje redacta la respuesta citando las secciones de las que procede.

El objetivo es que responda únicamente con el contenido de la tesis y que diga
explícitamente cuándo la información no está en ella, en lugar de inventarla.

La interfaz muestra, junto a cada respuesta, los fragmentos recuperados con sus
ecuaciones renderizadas y las figuras originales de la tesis con sus pies.

**Estado: funcional en local.** Queda el despliegue público.

---

## Cómo funciona

```
tesis.docx  (251 MB, 158 páginas)
    │
    ├── convertir.py ............ pandoc: .docx → Markdown
    │                              ecuaciones a LaTeX, tablas,
    │                              extracción y compresión de figuras
    │
    ├── arreglar_encabezados.py .. repara la jerarquía usando python-docx
    │                              como fuente de referencia
    │
    ├── ingest.py ............... Markdown → 76 secciones con ruta jerárquica
    │                              y figuras emparejadas con sus pies
    │
    ├── chunk.py ................ 444 fragmentos de ~875 caracteres
    │                              con solape de 2 frases completas
    │
    ├── embed.py ................ 444 vectores de 768 dimensiones
    │                              (modelo multilingüe, ejecutado en local)
    │
    ├── retrieve.py ............. similitud coseno → los 5 fragmentos más cercanos
    │
    └── generate.py ............. el LLM redacta la respuesta con citas de sección
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
| Procesado de figuras | Pillow | 0 € |
| Embeddings | `intfloat/multilingual-e5-base` (local) | 0 € |
| Búsqueda vectorial | numpy | 0 € |
| Generación | Ollama + `qwen2.5:14b` (local) | 0 € |
| Interfaz | Streamlit | 0 € |

Todo el pipeline corre en local sin coste. Para el despliegue público está previsto el
patrón **BYOK** (*Bring Your Own Key*): cada visitante introduce su propia clave de
API para la parte de generación, de forma que nadie paga el consumo de otros.

---

## Requisitos previos

- Python 3.12
- [pandoc](https://pandoc.org) — `brew install pandoc` en macOS
- [Ollama](https://ollama.com) — `brew install ollama`, y después
  `ollama pull qwen2.5:14b`

## Uso

1. Descarga la tesis en formato `.docx` desde
   [Zenodo](https://doi.org/10.5281/zenodo.22911361) y colócala en `data/raw/`.

2. Instala las dependencias:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

3. Ejecuta el pipeline (cada paso depende del anterior):

```bash
python -m src.convertir              # .docx → markdown; extrae y comprime las figuras
python -m src.arreglar_encabezados   # repara encabezados y fórmulas
python -m src.ingest                 # markdown → secciones con figuras y pies
python -m src.chunk                  # secciones → fragmentos
python -m src.embed                  # fragmentos → vectores
```

4. Con `ollama serve` corriendo en otra terminal:

```bash
python -m streamlit run app.py       # interfaz web
```

También se puede usar desde la terminal, sin interfaz:

```bash
python -m src.generate               # preguntas y respuestas
python -m src.retrieve               # solo el buscador, sin generación
```

---

## Estructura del proyecto

```
ask-my-thesis/
├── app.py                        # interfaz web (Streamlit)
├── data/
│   ├── raw/                      # tesis original (no versionada: 251 MB)
│   ├── media/                    # figuras comprimidas (12 MB, versionadas)
│   ├── processed/                # archivos intermedios (no versionados)
│   ├── preguntas.json            # set de evaluación (41 preguntas)
│   └── notas/                    # puntuaciones manuales de la evaluación
├── src/
│   ├── convertir.py
│   ├── arreglar_encabezados.py
│   ├── ingest.py
│   ├── chunk.py
│   ├── embed.py
│   ├── retrieve.py
│   ├── generate.py
│   ├── evaluar_retrieval.py
│   ├── evaluar_generacion.py
│   └── puntuar.py
├── notebooks/                    # scripts de exploración y verificación
├── requirements.txt
├── LICENSE
└── README.md
```

Las figuras se versionan porque la aplicación desplegada las necesita y, tras
comprimirlas, ocupan poco (155 MB → 12 MB). Los archivos intermedios de
`data/processed/` no, porque se regeneran ejecutando el pipeline. La regla aplicada:
**en el repositorio va lo que no se puede reconstruir**.

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
los pies de figura. El texto útil pasó de 292.209 a 337.796 caracteres, y las
secciones con ecuaciones de 0 a 40.

Como contrapartida, pandoc no reconoció 5 de los 82 encabezados del documento e
importó las cabeceras de página al cuerpo del texto, partiendo frases por la mitad.
Por eso `arreglar_encabezados.py` usa python-docx como fuente de referencia de la
estructura para parchear la salida de pandoc: **cada herramienta para lo que acierta**.
Se recuperan los 5 encabezados perdidos y se eliminan 111 cabeceras de página.

### Figuras: SVG, gemelos PNG y compresión

81 de las 95 figuras estaban guardadas como SVG, que se visualizaban con pérdidas de
contenido. Word guarda junto a cada SVG una copia PNG de respaldo, así que el pipeline
extrae esos PNG del ZIP y reescribe las referencias del Markdown. 81 de 81 redirigidas
correctamente.

Después se aplanan sobre fondo blanco (necesario porque el JPEG no admite
transparencia), se redimensionan a 1400 px de ancho y se guardan como JPEG de calidad
85. El resultado pasa de 155 MB a 12 MB, que es lo que hace viable versionarlas y
desplegar la aplicación.

### Emparejado de figuras y pies

Las 62 figuras de los capítulos se muestran junto a su pie original. Conseguirlo
requirió cubrir cuatro disposiciones distintas en el Markdown de pandoc: el pie en la
línea siguiente, en la misma línea tras los atributos de la imagen, a cuatro líneas
con un ancla suelta en medio, y a diez líneas con el prefijo `:` de pie de tabla.

Para poder buscar lejos sin riesgo de emparejar una figura con el pie de la siguiente,
la búsqueda se detiene en cuanto encuentra otra imagen. Resultado: 62 de 62 figuras
con pie, ninguno duplicado.

### Chunking

Tamaño **objetivo** de 1.000 caracteres: si una frase o una ecuación no cabe, el
fragmento se pasa de tamaño antes que partirla. Cuatro reglas:

- **Corte por frases**, no por número de caracteres, para no partir ideas a la mitad.
- **Fórmulas protegidas**: antes de cortar nada, cada expresión LaTeX se sustituye por
  un marcador numerado que no contiene puntos ni saltos de línea, y se restituye
  después. Así ningún criterio de corte puede partir una fórmula, ni siquiera las de
  bloque que ocupan varias líneas. No es una comprobación: es imposible por
  construcción.
- **Solape por frases**: cada fragmento arranca repitiendo las dos últimas frases
  completas del anterior, con sus ecuaciones dentro. La versión anterior arrastraba los
  últimos 150 caracteres a ciegas, lo que cortaba fórmulas por la mitad en el 4 % de
  los fragmentos.
- **Fusión de huérfanos**: un resto final de menos de 300 caracteres se une al
  fragmento anterior en vez de quedar suelto sin contexto.

Cada fragmento lleva delante su ruta jerárquica completa
(`Chapter 4 > 4.3 Electronic Structure > 4.3.1 C90 on Au(111)`) **dentro del texto que
se vectoriza**. Esto resuelve el problema de las secciones con títulos idénticos:
`4.2.1 C90 on Au(111)` y `4.3.1 C90 on Au(111)` hablan de cosas distintas, y la ruta
las separa en el espacio de embeddings.

Distribución resultante: media 874 caracteres, mínimo 304, máximo 1.262. Y el dato que
importa: **0 de 444 fragmentos contienen una fórmula partida** (delimitadores sin
pareja o llaves descuadradas), frente a 17 antes del cambio.

### Un bug silencioso: los subíndices desaparecidos

El Markdown que produce pandoc viene lleno de marcas de énfasis (`**Figure 4.5**`,
`**a)**`), que son ruido tanto para el modelo de embeddings como para el contexto del
LLM. El pipeline las eliminaba con una expresión regular que borraba rachas de uno a
tres `*` o `_`.

El problema es que **en LaTeX el guion bajo es el subíndice**. Esa limpieza se llevaba
por delante `k_{1}`, `E_{F}`, `V_{bias}` y todos los demás, en toda la tesis. El
sistema no fallaba de forma visible: simplemente indexaba y le entregaba al modelo
fórmulas como `T1D` y `k12`, que el modelo reproducía fielmente.

Se localizó por bisección sobre las etapas del pipeline —comprobando en qué archivo
intermedio desaparecía una cadena concreta— y se cuantificó antes de corregirlo:

| Alcance del regex | Cambios en prosa | Cambios dentro de fórmulas |
|---|---|---|
| `[*_]{1,3}` (original) | 1.827 | 513 |
| `[*]{2,3}` (actual) | 1.552 | **0** |

En toda la tesis, el guion bajo **no aparece ni una sola vez** como marca de énfasis
fuera de una fórmula: pandoc usa asteriscos. Y `**`, `__`, `***` o `___` no significan
nada en LaTeX —`a__b` es un error de compilación—, así que acotar el regex a rachas de
dos o tres asteriscos conserva el 85 % de la limpieza sin poder tocar una fórmula. No
es seguro por casualidad estadística: lo es por construcción.

El efecto sobre el sistema se ve en el recall estricto, más abajo: 73 % → 91 %.

### Modelo de embeddings multilingüe

La tesis está en inglés y las preguntas pueden ser en español. Un modelo monolingüe
situaría "corriente túnel" y "tunnelling current" en puntos alejados del espacio
vectorial y el sistema no encontraría nada. `multilingual-e5-base` los alinea.

Los vectores se normalizan a longitud 1, de forma que la similitud coseno se reduce a
un producto escalar y la búsqueda sobre los 444 fragmentos es una única multiplicación
matriz-vector.

### Secciones excluidas del índice

`Agradecimientos`, `Resumen`, `Chapter 8: Conclusiones Generales` y `References`.

El caso interesante es el **Resumen**: al ser un texto que menciona todos los temas de
la tesis sin profundizar en ninguno, su vector quedaba en una posición central del
espacio semántico y aparecía entre los resultados de casi cualquier pregunta,
desplazando a las secciones que sí contenían la respuesta.

### Capa de abstracción entre backends

`generate.py` expone `generar_respuesta()` y `generar_respuesta_stream()`, más un
registro de backends disponibles. El resto del código no sabe si por debajo se está
hablando con Ollama en `localhost` o con una API remota.

Esto no es un ejercicio de estilo: el modelo local no cabe en la memoria del servidor
donde se desplegará la aplicación, así que el sistema tiene que poder usar los dos sin
cambiar nada más.

Hay tres backends (Ollama, Anthropic y Google), cada uno con su versión normal y su
versión en *streaming*, y todos con la misma firma. Las peticiones HTTP se construyen
con `urllib` de la biblioteca estándar, igual que las de Ollama: **ninguna dependencia
nueva**, lo que importa en un servidor con memoria justa. Los códigos de error del
proveedor se traducen a frases que un visitante entiende ("la clave no es válida", "el
modelo está saturado") en lugar de propagar una traza de Python a la interfaz.

### Renderizado de LaTeX en la interfaz

La interfaz **parte el texto por los `$`** y evalúa cada trozo por separado: es fórmula
si contiene marcadores inequívocos de LaTeX (`{`, `}`, `\`, `=`) y si sus delimitadores
estructurales (`\left`/`\right`, `\begin`/`\end`, llaves) están balanceados. Los trozos
que no lo son se muestran como texto plano, y los subíndices y superíndices de pandoc
(`C~90~`, `2.6^o^`) se traducen a LaTeX para que se rendericen bien.

Esto se escribió cuando el chunking partía fórmulas y los fragmentos llegaban con
delimitadores sin pareja. Desde que el troceo las respeta, **la red de seguridad casi
nunca se activa**: queda para la salida del modelo de lenguaje, que no siempre respeta
el formato que se le pide.

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

### Recuperación

| k | Recall (alguna sección) | Recall (todas) | Posición media del 1er acierto |
|---|---|---|---|
| 3 | 78 % | 69 % | 1,3 |
| 5 | 89 % | 83 % | 1,7 |
| 10 | 89 % | 86 % | 1,7 |

Por tipo de pregunta, con k = 5: comparativa, fórmula y numérica 100 %, general 83 %,
factual 77 %.

**k = 5 es el punto de equilibrio.** Pasar de 5 a 10 fragmentos no mejora el recall por
sección (89 % → 89 %) ni el estricto (91 % → 91 %), y duplica el contexto que hay que
pagar en cada llamada al modelo.

### El recall por sección sobreestima el resultado

Once preguntas llevan anotado además el **dato concreto** que la respuesta necesita
(un valor, una expresión). Comprobar si ese dato llega de verdad al contexto es una
métrica más exigente, y fue la que delató el bug de los subíndices:

| Métrica | Antes del arreglo (k = 5) | Ahora (k = 5) |
|---|---|---|
| Recall por sección | 86 % | 89 % |
| Recall estricto (el dato llega) | 73 % | **91 %** |

El recall por sección apenas se movió, y era de esperar: los embeddings se apoyan en la
prosa, que no cambió. Con 36 preguntas, una pregunta vale 2,8 puntos, así que esas
diferencias son ruido.

El recall estricto sí dio un salto de 18 puntos, y la razón es directa: varias de esas
once cadenas son expresiones LaTeX (`\varphi(x) = \left\{ \begin{array}{r}`,
`Norm.\ \mathrm{\Delta}Purcell = \ \frac`). Mientras los subíndices estaban rotos,
**esas cadenas no podían aparecer en el índice**, así que el buscador no tenía forma de
acertar. No era un problema de recuperación: era un problema de datos.

Queda un fallo de once: una fórmula cuya sección sí se recupera, pero que cae en el
fragmento vecino al que trae la respuesta.

La diferencia que persiste entre las dos métricas se explica porque una sección larga
se reparte en varios fragmentos, y el recall por sección da por bueno cualquiera de
ellos aunque no contenga el dato.

### El umbral de similitud no discrimina

| Grupo | Similitud media | Mínimo | Máximo |
|---|---|---|---|
| Preguntas con respuesta en la tesis | 0,836 | 0,755 | — |
| Preguntas trampa | 0,833 | — | 0,872 |

Las dos distribuciones están superpuestas: la pregunta trampa con mayor similitud
supera a cualquier pregunta legítima, y la más baja de estas queda por debajo de la
media de las trampas. **No existe ningún umbral que separe ambos grupos**, lo que
descarta filtrar por similitud y obliga a delegar la abstención en el modelo de
lenguaje mediante instrucciones explícitas.

### Generación

Cada respuesta se puntuó a mano en dos criterios (correcta y completa) sobre una
escala de tres valores. Con k = 5:

| Configuración | Correcta (sí) | Completa (sí) | Tiempo medio |
|---|---|---|---|
| qwen2.5:7b, prompt v1 | 71 % | 68 % | 12,2 s |
| qwen2.5:14b, prompt v1 | 73 % | 71 % | 20,5 s |
| qwen2.5:14b, prompt v2 | **80 %** | **80 %** | 25,7 s |

Las cinco preguntas trampa se responden con la abstención correcta en todas las
configuraciones.

El salto de la v1 a la v2 del prompt viene de dos cambios concretos: fijar el idioma
de la respuesta **por código** en lugar de pedírselo al modelo, y exigir el registro
tentativo propio de un texto científico ("esto sugiere", "los datos indican") en lugar
de afirmaciones rotundas.

### Un prompt mejor no mejora todos los modelos

El mismo prompt v2 aplicado al modelo de 7B **empeoró** su resultado: las abstenciones
indebidas pasaron de 4 a 7, y las tres nuevas eran preguntas numéricas que antes
respondía correctamente. La regla añadida para evitar alucinaciones de datos ("cada
número debe aparecer en los fragmentos") fue interpretada por el modelo pequeño como
una orden de abstenerse ante la duda.

El modelo de 14B absorbe el mismo prompt sin degradarse. La capacidad de sostener
varias instrucciones simultáneas escala con el tamaño del modelo, y eso hace que una
mejora de prompt no sea automáticamente una mejora del sistema.

### Un fallo de generación rastreado hasta los datos

Una pregunta concreta provocaba que el modelo colapsara a caracteres chinos a mitad de
la respuesta, de forma reproducible y siempre en el mismo punto de la frase. La
palabra que aparecía (偏置) significa "bias".

El contexto de esa pregunta contenía una fórmula con `V_bias` **mal formada**, con el
paréntesis de cierre fuera del bloque LaTeX. Esa fórmula estaba así en el documento
original y se había copiado y pegado siete veces. Repararla en el pipeline, sin tocar
la fuente, eliminó el colapso.

Como red de seguridad se mantienen dos barreras en el código: tokens de parada que
cortan la generación si el modelo empieza a reescribir la plantilla, y una validación
que detecta caracteres CJK en la respuesta.

---

## Limitaciones conocidas

- **El dato concreto no siempre llega.** El recall estricto (91 %) sigue por debajo del
  recall por sección (89 % de secciones correctas no garantiza el fragmento correcto).
  El caso que falla es una expresión matemática que cae en el fragmento contiguo.

- **Redundancia en la recuperación.** Con frecuencia los 5 fragmentos recuperados
  pertenecen a la misma sección, desaprovechando contexto que podría cubrir el tema
  desde varios ángulos. Una técnica de diversificación (MMR) lo mitigaría.

- **Las figuras se asocian a la sección, no al fragmento.** Todos los fragmentos de una
  sección arrastran todas sus figuras, de modo que al recuperar varios fragmentos
  vecinos la interfaz repite la misma imagen.

- **Preguntas de alcance amplio.** "¿De qué trata la tesis?" requiere información
  repartida por todo el documento y el sistema solo dispone de 5 fragmentos. Es una
  limitación estructural del RAG básico, no un fallo de implementación.

- **Ambigüedad de las preguntas.** "¿Qué significa HOMO?" admite dos lecturas —el
  desarrollo de la sigla o el concepto físico— y el sistema resuelve la segunda. El
  86 % de recall no es un techo del sistema sino un reflejo de esa ambigüedad
  inherente al lenguaje natural, que técnicas como la reescritura de consultas o la
  memoria conversacional mitigarían.

- **Las referencias bibliográficas están desconectadas.** El texto contiene `[42]` y
  la bibliografía contiene la entrada 42, pero nada las enlaza. Es resoluble con una
  búsqueda en diccionario, no con RAG.

---

## Pendiente

- [x] Backends de API (Anthropic, Google) con traducción de errores HTTP a mensajes
      legibles
- [x] Selector de proveedor y campo de clave en la interfaz: la clave vive solo en la
      sesión del visitante, nunca se escribe en disco ni en los registros
- [ ] Reintentos con espera creciente: el nivel gratuito de Google devuelve 503 con
      frecuencia
- [ ] Despliegue público con BYOK
- [ ] *(opcional)* Búsqueda híbrida vectorial + BM25
- [ ] *(opcional)* Diversificación de resultados (MMR)
- [ ] *(opcional)* API propia con FastAPI
- [ ] *(opcional)* Enlazar las citas `[N]` con la bibliografía

---

## Datos

El pipeline parte del documento original en formato `.docx` (251 MB), que no se
incluye en el repositorio por tamaño. Descárgalo desde Zenodo y colócalo en
`data/raw/`:

**https://doi.org/10.5281/zenodo.22911361**

La versión oficial de la tesis, en PDF, está depositada en
[Biblos-e Archive (UAM)](http://hdl.handle.net/10486/715334). El pipeline usa el
`.docx` porque conserva las ecuaciones en formato editable y la estructura de
secciones, que se pierden al extraer texto de un PDF.

## Licencia

El código de este proyecto se publica bajo licencia MIT.

La tesis es obra del autor y está depositada en Biblos-e Archive (UAM) y en Zenodo
bajo licencia CC BY-NC-ND 4.0: su reutilización requiere citar la fuente, reconocer la
autoría, no obtener beneficio comercial y no realizar obras derivadas.