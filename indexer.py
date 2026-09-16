"""Escaneo del disco y actualización del índice de archivos en SQLite."""

import os
import sqlite3
import threading
from datetime import datetime, timezone

import psutil
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from config import CARPETAS_EXCLUIDAS
from db import conectar


def _ruta_excluida(ruta: str) -> bool:
    partes = ruta.lower().replace("\\", "/").split("/")
    return any(parte in CARPETAS_EXCLUIDAS for parte in partes)


def _unidades_disponibles() -> list[str]:
    return [p.mountpoint for p in psutil.disk_partitions(all=False) if "cdrom" not in p.opts]


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def escanear_unidad(unidad: str, conexion: sqlite3.Connection, on_archivo=None) -> int:
    """Recorre una unidad completa y guarda cada archivo encontrado. Devuelve el total indexado."""
    total = 0
    cursor = conexion.cursor()

    for carpeta_actual, subcarpetas, archivos in os.walk(unidad, onerror=lambda e: None):
        if _ruta_excluida(carpeta_actual):
            subcarpetas[:] = []
            continue
        subcarpetas[:] = [d for d in subcarpetas if d.lower() not in CARPETAS_EXCLUIDAS]

        for nombre_archivo in archivos:
            ruta_completa = os.path.join(carpeta_actual, nombre_archivo)
            try:
                info = os.stat(ruta_completa)
            except OSError:
                continue

            extension = os.path.splitext(nombre_archivo)[1].lstrip(".").lower()
            cursor.execute(
                """
                INSERT INTO archivos (ruta, nombre, extension, tamano_bytes,
                                       fecha_creacion, fecha_modificacion, unidad)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ruta) DO UPDATE SET
                    tamano_bytes = excluded.tamano_bytes,
                    fecha_modificacion = excluded.fecha_modificacion
                """,
                (
                    ruta_completa,
                    nombre_archivo,
                    extension,
                    info.st_size,
                    _iso(info.st_ctime),
                    _iso(info.st_mtime),
                    unidad,
                ),
            )
            total += 1
            if on_archivo and total % 500 == 0:
                on_archivo(total, ruta_completa)

    conexion.commit()
    return total


def indexar_todo_el_disco(on_archivo=None) -> int:
    """Escanea todas las unidades detectadas y las guarda en el índice."""
    conexion = conectar()
    total = 0
    try:
        for unidad in _unidades_disponibles():
            total += escanear_unidad(unidad, conexion, on_archivo=on_archivo)
    finally:
        conexion.close()
    return total


def _indexar_un_archivo(conexion: sqlite3.Connection, ruta_completa: str) -> None:
    try:
        info = os.stat(ruta_completa)
    except OSError:
        return

    nombre_archivo = os.path.basename(ruta_completa)
    extension = os.path.splitext(nombre_archivo)[1].lstrip(".").lower()
    unidad = os.path.splitdrive(ruta_completa)[0] + "\\"
    conexion.execute(
        """
        INSERT INTO archivos (ruta, nombre, extension, tamano_bytes,
                               fecha_creacion, fecha_modificacion, unidad)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ruta) DO UPDATE SET
            tamano_bytes = excluded.tamano_bytes,
            fecha_modificacion = excluded.fecha_modificacion
        """,
        (
            ruta_completa,
            nombre_archivo,
            extension,
            info.st_size,
            _iso(info.st_ctime),
            _iso(info.st_mtime),
            unidad,
        ),
    )
    conexion.commit()


def _eliminar_archivo(conexion: sqlite3.Connection, ruta_completa: str) -> None:
    conexion.execute("DELETE FROM archivos WHERE ruta = ?", (ruta_completa,))
    conexion.commit()


class _ManejadorCambios(FileSystemEventHandler):
    """Mantiene el índice sincronizado ante cambios detectados por watchdog."""

    def __init__(self):
        # Cada hilo de watchdog necesita su propia conexión SQLite.
        self._local = threading.local()

    def _conexion(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conexion"):
            self._local.conexion = conectar()
        return self._local.conexion

    def on_created(self, event):
        if not event.is_directory and not _ruta_excluida(event.src_path):
            _indexar_un_archivo(self._conexion(), event.src_path)

    def on_modified(self, event):
        if not event.is_directory and not _ruta_excluida(event.src_path):
            _indexar_un_archivo(self._conexion(), event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            _eliminar_archivo(self._conexion(), event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            _eliminar_archivo(self._conexion(), event.src_path)
            if not _ruta_excluida(event.dest_path):
                _indexar_un_archivo(self._conexion(), event.dest_path)


class VigilanteMultiUnidad:
    """Agrupa un Observer de watchdog por unidad para que una unidad no observable
    (ej. un lector de tarjetas vacío o un volumen sin sistema de archivos reconocido)
    no impida vigilar el resto."""

    def __init__(self, observers: list[Observer]):
        self._observers = observers

    def stop(self):
        for observer in self._observers:
            observer.stop()

    def join(self, timeout: float | None = None):
        for observer in self._observers:
            observer.join(timeout=timeout)


def iniciar_watcher() -> VigilanteMultiUnidad:
    """Arranca un watcher en segundo plano que mantiene el índice actualizado.

    Cada unidad se observa con su propio Observer para que si una unidad no se
    puede vigilar (permisos, sin sistema de archivos, etc.) las demás sigan
    funcionando con normalidad. Devuelve un objeto con `.stop()` + `.join()`.
    """
    manejador = _ManejadorCambios()
    observers: list[Observer] = []
    for unidad in _unidades_disponibles():
        observer = Observer()
        observer.schedule(manejador, unidad, recursive=True)
        try:
            observer.start()
        except OSError:
            continue
        observers.append(observer)
    return VigilanteMultiUnidad(observers)


if __name__ == "__main__":
    def reportar(total, ruta):
        print(f"Indexados: {total} (último: {ruta})")

    encontrados = indexar_todo_el_disco(on_archivo=reportar)
    print(f"\nIndexado inicial completo. Total de archivos: {encontrados}")
