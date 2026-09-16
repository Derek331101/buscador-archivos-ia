"""Esquema y conexión a la base de datos SQLite del índice de archivos."""

import sqlite3

from config import DATA_DIR, DB_PATH

ESQUEMA = """
CREATE TABLE IF NOT EXISTS archivos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruta TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    extension TEXT,
    tamano_bytes INTEGER,
    fecha_creacion TEXT,
    fecha_modificacion TEXT,
    unidad TEXT
);

CREATE INDEX IF NOT EXISTS idx_archivos_nombre ON archivos (nombre);
CREATE INDEX IF NOT EXISTS idx_archivos_extension ON archivos (extension);
CREATE INDEX IF NOT EXISTS idx_archivos_fecha_mod ON archivos (fecha_modificacion);
"""


def conectar() -> sqlite3.Connection:
    """Abre (y crea si hace falta) la conexión a la base de datos del índice."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(DB_PATH)
    conexion.execute("PRAGMA journal_mode=WAL;")
    conexion.executescript(ESQUEMA)
    return conexion
