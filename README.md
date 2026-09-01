# Ask My Thesis
Este proyecto es un RAG que conoce mi tesis doctoral y responde a las preguntas relacionadas con la misma. Todo ello desplegado en una aplicación web con Streamlit a la que se le escribirán las preguntas. El programa evaluará si dichas preguntas están relacionadas con mi tesis doctoral y si lo están, darán una respuesta e indicará qué partes de la tesis responden mejor a dicha pregunta

## Stack
- Python
- python-docx (extracción del documento)
- sentence-transformers (embeddings, ejecutados en local)
- ChromaDB (base de datos vectorial)
- Ollama / API (generación de respuestas)
- Streamlit (interfaz)

## Datos

La tesis no se incluye en este repositorio por tamaño (251 MB en formato .docx). Descárgala desde [Biblos-e Archive (UAM)](http://hdl.handle.net/10486/715334) y colócala en `data/raw/`.

## Licencia

El código de este proyecto se publica bajo licencia MIT.

La tesis depositada en Biblos-e Archive (UAM) es obra del autor y su reutilización requiere citar la fuente, reconocer la autoría, no obtener beneficio comercial y no realizar obras derivadas (equivalente a CC BY-NC-ND).

