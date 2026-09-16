"""Cliente de Ollama: traduce lenguaje natural a filtros de búsqueda estructurados."""

import json

import requests

from config import OLLAMA_MODEL, OLLAMA_URL
from search_engine import Filtros

PROMPT_SISTEMA = """Eres el módulo de interpretación de un buscador de archivos local.
El usuario describe en lenguaje natural el archivo que busca. Tu única tarea es
responder SIEMPRE con un JSON válido, sin texto adicional, con este esquema exacto:

{
  "nombre_parcial": string o null,
  "extension": string o null (sin el punto, ej. "pdf"),
  "fecha_desde": string o null (formato "YYYY-MM-DD"),
  "fecha_hasta": string o null (formato "YYYY-MM-DD"),
  "tamano_min": number o null (bytes),
  "tamano_max": number o null (bytes),
  "pregunta_aclaracion": string o null
}

Reglas:
- Nunca inventes una ruta de archivo ni un nombre exacto que el usuario no haya dado.
- Si la descripción es vaga (por ejemplo, faltan tanto nombre como extensión como fecha),
  deja "pregunta_aclaracion" con UNA sola pregunta corta en español que pida el dato más
  útil para acotar la búsqueda (extensión, fecha aproximada, o palabra clave del nombre).
- Si ya tienes suficiente información, deja "pregunta_aclaracion" en null.
- Responde solo el JSON, sin explicaciones ni markdown.
"""


class OllamaNoDisponible(Exception):
    pass


def _consultar_ollama(mensaje: str, historial: list[dict] | None = None) -> str:
    mensajes = [{"role": "system", "content": PROMPT_SISTEMA}]
    mensajes.extend(historial or [])
    mensajes.append({"role": "user", "content": mensaje})

    try:
        respuesta = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": mensajes, "stream": False},
            timeout=300,
        )
        respuesta.raise_for_status()
    except requests.exceptions.Timeout as error:
        raise OllamaNoDisponible(
            f"El modelo '{OLLAMA_MODEL}' tardó demasiado en responder (más de 5 minutos). "
            "Si es un modelo grande, la primera respuesta puede tardar mientras carga en memoria; "
            "intenta de nuevo."
        ) from error
    except requests.exceptions.RequestException as error:
        raise OllamaNoDisponible(
            f"No se pudo conectar con Ollama en {OLLAMA_URL}. "
            "Asegúrate de que esté corriendo (`ollama serve`)."
        ) from error

    return respuesta.json()["message"]["content"]


def interpretar(mensaje: str, historial: list[dict] | None = None) -> tuple[Filtros, str | None]:
    """Convierte un mensaje del usuario en Filtros estructurados + posible pregunta de aclaración.

    Si se pasa `historial` (lista mutable de mensajes {role, content}), se le agregan
    el turno del usuario y la respuesta del modelo para que la conversación mantenga
    contexto en llamadas posteriores.
    """
    contenido = _consultar_ollama(mensaje, historial)

    if historial is not None:
        historial.append({"role": "user", "content": mensaje})
        historial.append({"role": "assistant", "content": contenido})

    try:
        datos = json.loads(contenido)
    except json.JSONDecodeError:
        inicio, fin = contenido.find("{"), contenido.rfind("}")
        if inicio == -1 or fin == -1:
            return Filtros(), "No entendí bien tu descripción, ¿puedes darme más detalles del archivo?"
        datos = json.loads(contenido[inicio : fin + 1])

    filtros = Filtros(
        nombre_parcial=datos.get("nombre_parcial"),
        extension=datos.get("extension"),
        fecha_desde=datos.get("fecha_desde"),
        fecha_hasta=datos.get("fecha_hasta"),
        tamano_min=datos.get("tamano_min"),
        tamano_max=datos.get("tamano_max"),
    )
    return filtros, datos.get("pregunta_aclaracion")


def generar_pregunta_sin_resultados(historial: list[dict]) -> str:
    """Pide al modelo una siguiente pregunta de aclaración cuando la búsqueda no dio resultados."""
    aviso = (
        "La búsqueda con esos filtros no encontró ningún archivo. "
        "Genera una nueva 'pregunta_aclaracion' pidiendo un dato distinto que ayude a "
        "encontrar el archivo (por ejemplo carpeta aproximada, otra palabra clave, o un "
        "rango de fechas más amplio). Devuelve el mismo JSON de siempre."
    )
    _, pregunta = interpretar(aviso, historial)
    return pregunta or "No logré encontrar el archivo. ¿Tienes alguna otra pista sobre él?"


if __name__ == "__main__":
    filtros, pregunta = interpretar("busco un pdf de facturas de marzo")
    print("Filtros:", filtros)
    print("Pregunta de aclaración:", pregunta)
