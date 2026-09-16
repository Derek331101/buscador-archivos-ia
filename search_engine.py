"""Búsqueda de archivos en el índice a partir de filtros estructurados."""

import sqlite3
from dataclasses import dataclass

from config import MAX_RESULTADOS
from db import conectar


@dataclass
class Filtros:
    nombre_parcial: str | None = None
    extension: str | None = None
    fecha_desde: str | None = None  # ISO 8601, ej. "2025-03-01"
    fecha_hasta: str | None = None
    tamano_min: int | None = None
    tamano_max: int | None = None


def buscar(filtros: Filtros, conexion: sqlite3.Connection | None = None) -> list[dict]:
    """Ejecuta la búsqueda en el índice y devuelve una lista de archivos candidatos."""
    cerrar_al_final = conexion is None
    conexion = conexion or conectar()

    condiciones = []
    parametros: list = []

    if filtros.nombre_parcial:
        condiciones.append("nombre LIKE ?")
        parametros.append(f"%{filtros.nombre_parcial}%")
    if filtros.extension:
        condiciones.append("extension = ?")
        parametros.append(filtros.extension.lstrip(".").lower())
    if filtros.fecha_desde:
        condiciones.append("fecha_modificacion >= ?")
        parametros.append(filtros.fecha_desde)
    if filtros.fecha_hasta:
        condiciones.append("fecha_modificacion <= ?")
        parametros.append(filtros.fecha_hasta)
    if filtros.tamano_min is not None:
        condiciones.append("tamano_bytes >= ?")
        parametros.append(filtros.tamano_min)
    if filtros.tamano_max is not None:
        condiciones.append("tamano_bytes <= ?")
        parametros.append(filtros.tamano_max)

    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    consulta = f"""
        SELECT nombre, ruta, extension, tamano_bytes, fecha_creacion, fecha_modificacion
        FROM archivos
        {where}
        ORDER BY
            CASE WHEN nombre = ? THEN 0 ELSE 1 END,
            fecha_modificacion DESC
        LIMIT ?
    """
    parametros_ordenados = [*parametros, filtros.nombre_parcial or "", MAX_RESULTADOS]

    try:
        cursor = conexion.execute(consulta, parametros_ordenados)
        columnas = [d[0] for d in cursor.description]
        return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        if cerrar_al_final:
            conexion.close()


if __name__ == "__main__":
    resultados = buscar(Filtros(extension="url"))
    for r in resultados:
        print(r)
