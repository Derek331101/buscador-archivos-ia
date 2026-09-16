# Buscador de archivos con IA

Aplicación de escritorio que corre de forma nativa y offline en Windows para
encontrar archivos en tu disco describiéndolos en lenguaje natural, en vez de
recordar la ruta exacta.

## ¿Cómo funciona?

1. Al abrir la app, se indexa todo el disco (nombre, extensión, tamaño y
   fechas de cada archivo) en una base de datos local (SQLite). Este primer
   indexado tarda unos minutos según el tamaño de tu disco.
2. Escribes en el chat qué archivo buscas (ej. *"un pdf de facturas de
   marzo"*), y un modelo de lenguaje local (vía [Ollama](https://ollama.com))
   interpreta tu descripción y la traduce en filtros de búsqueda.
3. Si no encuentra nada, la IA te hace preguntas de seguimiento para acotar
   la búsqueda (extensión, fecha aproximada, palabra clave, etc.).
4. Cuando encuentra el archivo, puedes abrir su ubicación directamente en el
   Explorador de Windows con un botón.
5. Mientras la app está abierta, un watcher vigila cambios en el disco
   (archivos nuevos, movidos, borrados) para mantener el índice actualizado
   sin tener que re-escanear todo de nuevo.

## Requisitos previos

- **Python 3.11+**
- **[Ollama](https://ollama.com)** instalado y corriendo, con un modelo
  descargado. Por defecto la app usa `phi3` (ligero, corre bien en CPU sin
  GPU dedicada):

  ```
  ollama pull phi3
  ```

  Si tienes una GPU potente, puedes usar un modelo más grande cambiando
  `OLLAMA_MODEL` en [`config.py`](config.py).

## Instalación

```
pip install -r requirements.txt
```

## Uso

```
python main.py
```

La primera vez, espera a que el indicador de estado diga "Índice actualizado"
antes de esperar resultados completos — hasta entonces solo se han indexado
las carpetas ya recorridas.

## Estructura del proyecto

| Archivo | Responsabilidad |
|---|---|
| `main.py` | Punto de entrada: verifica que Ollama esté corriendo y lanza la GUI. |
| `gui.py` | Ventana principal (PySide6): chat, resultados, botón "Abrir ubicación". |
| `indexer.py` | Escaneo inicial del disco y watcher de cambios en segundo plano. |
| `search_engine.py` | Consultas al índice a partir de filtros estructurados. |
| `nlu.py` | Cliente de Ollama: traduce lenguaje natural a filtros y genera preguntas de aclaración. |
| `db.py` | Esquema y conexión a la base de datos SQLite del índice. |
| `config.py` | Configuración: carpetas excluidas, modelo de Ollama, rutas. |

## Notas

- La búsqueda es por **metadatos** (nombre, extensión, tamaño, fechas), no
  por contenido dentro de los archivos.
- Pensada para **Windows** (usa `explorer /select` para abrir ubicaciones).
- Carpetas de sistema (`Windows`, `Program Files`, `$Recycle.Bin`, etc.) se
  excluyen automáticamente del escaneo; puedes ajustar la lista en
  `config.py`.
