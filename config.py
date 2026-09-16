"""Configuración global del asistente de búsqueda de archivos."""

from pathlib import Path

# Ubicación de la base de datos de índice.
DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "archivos.db"

# Carpetas que se excluyen del escaneo (nombres, no rutas completas,
# se comparan en minúsculas contra cada segmento de la ruta).
CARPETAS_EXCLUIDAS = {
    "windows",
    "$recycle.bin",
    "programdata",
    "program files",
    "program files (x86)",
    "system volume information",
    "appdata",
    "node_modules",
    ".git",
    "__pycache__",
}

# Configuración de Ollama.
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "phi3"

# Máximo de resultados a mostrar por búsqueda.
MAX_RESULTADOS = 20
