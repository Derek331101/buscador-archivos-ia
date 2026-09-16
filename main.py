"""Punto de entrada del asistente de búsqueda de archivos."""

import sys

import requests

from config import OLLAMA_URL
from gui import iniciar_gui


def _ollama_disponible() -> bool:
    try:
        requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return True
    except requests.exceptions.RequestException:
        return False


def main():
    if not _ollama_disponible():
        print(
            f"No se detectó Ollama corriendo en {OLLAMA_URL}.\n"
            "Instálalo desde https://ollama.com, descarga un modelo "
            "(ej. 'ollama pull phi3') y asegúrate de que esté corriendo antes de "
            "iniciar esta aplicación.",
            file=sys.stderr,
        )
        sys.exit(1)

    iniciar_gui()


if __name__ == "__main__":
    main()
