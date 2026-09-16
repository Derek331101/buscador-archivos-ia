"""Ventana principal: chat de búsqueda de archivos + lista de resultados."""

import subprocess
import sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import nlu
import search_engine
from indexer import indexar_todo_el_disco, iniciar_watcher


class IndexadorThread(QThread):
    progreso = Signal(int, str)
    completado = Signal(int)

    def run(self):
        total = indexar_todo_el_disco(on_archivo=lambda n, ruta: self.progreso.emit(n, ruta))
        self.completado.emit(total)


class ConsultaThread(QThread):
    resultado_listo = Signal(list, str)
    error = Signal(str)

    def __init__(self, mensaje: str, historial: list[dict]):
        super().__init__()
        self.mensaje = mensaje
        self.historial = historial

    def run(self):
        try:
            filtros, pregunta = nlu.interpretar(self.mensaje, self.historial)

            if pregunta:
                self.resultado_listo.emit([], pregunta)
                return

            resultados = search_engine.buscar(filtros)
            if not resultados:
                pregunta_sin_resultados = nlu.generar_pregunta_sin_resultados(self.historial)
                self.resultado_listo.emit([], pregunta_sin_resultados)
                return

            self.resultado_listo.emit(resultados, "")
        except nlu.OllamaNoDisponible as error:
            self.error.emit(str(error))
        except Exception as error:  # noqa: BLE001 - se muestra al usuario tal cual
            self.error.emit(f"Ocurrió un error inesperado: {error}")


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Buscador de archivos con IA")
        self.resize(720, 560)

        self.historial: list[dict] = []
        self.indexador_thread: IndexadorThread | None = None
        self.consulta_thread: ConsultaThread | None = None
        self.observer = None

        self._construir_ui()
        self._iniciar_indexado()

    def _construir_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.estado_label = QLabel("Preparando índice de archivos...")
        layout.addWidget(self.estado_label)

        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        layout.addWidget(self.chat_area, stretch=1)

        entrada_layout = QHBoxLayout()
        self.entrada_texto = QLineEdit()
        self.entrada_texto.setPlaceholderText("¿Qué archivo necesitas buscar?")
        self.entrada_texto.returnPressed.connect(self._enviar_mensaje)
        entrada_layout.addWidget(self.entrada_texto)

        self.boton_enviar = QPushButton("Enviar")
        self.boton_enviar.clicked.connect(self._enviar_mensaje)
        entrada_layout.addWidget(self.boton_enviar)
        layout.addLayout(entrada_layout)

        layout.addWidget(QLabel("Resultados:"))
        self.lista_resultados = QListWidget()
        layout.addWidget(self.lista_resultados, stretch=1)

        self.boton_abrir = QPushButton("Abrir ubicación en el Explorador")
        self.boton_abrir.clicked.connect(self._abrir_ubicacion_seleccionada)
        self.boton_abrir.setEnabled(False)
        layout.addWidget(self.boton_abrir)

        self.lista_resultados.itemSelectionChanged.connect(
            lambda: self.boton_abrir.setEnabled(bool(self.lista_resultados.selectedItems()))
        )

        self._agregar_mensaje_chat("IA", "¿Qué archivo necesitas buscar?")

    def _agregar_mensaje_chat(self, autor: str, texto: str):
        self.chat_area.append(f"<b>{autor}:</b> {texto}")

    # --- Indexado inicial ---

    def _iniciar_indexado(self):
        self.indexador_thread = IndexadorThread()
        self.indexador_thread.progreso.connect(self._on_progreso_indexado)
        self.indexador_thread.completado.connect(self._on_indexado_completo)
        self.indexador_thread.start()

    def _on_progreso_indexado(self, total: int, ruta: str):
        self.estado_label.setText(f"Indexando... {total} archivos encontrados")

    def _on_indexado_completo(self, total: int):
        self.estado_label.setText(f"Índice actualizado ({total} archivos). Puedes buscar.")
        self.observer = iniciar_watcher()

    # --- Conversación de búsqueda ---

    def _enviar_mensaje(self):
        mensaje = self.entrada_texto.text().strip()
        if not mensaje or (self.consulta_thread and self.consulta_thread.isRunning()):
            return

        self._agregar_mensaje_chat("Tú", mensaje)
        self.entrada_texto.clear()
        self.boton_enviar.setEnabled(False)
        self.lista_resultados.clear()
        self.boton_abrir.setEnabled(False)

        self.consulta_thread = ConsultaThread(mensaje, self.historial)
        self.consulta_thread.resultado_listo.connect(self._on_resultado)
        self.consulta_thread.error.connect(self._on_error)
        self.consulta_thread.start()

    def _on_resultado(self, resultados: list, pregunta: str):
        self.boton_enviar.setEnabled(True)
        if pregunta:
            self._agregar_mensaje_chat("IA", pregunta)
            return

        self._agregar_mensaje_chat("IA", f"Encontré {len(resultados)} archivo(s) posible(s):")
        for r in resultados:
            texto = f"{r['nombre']}  —  {r['ruta']}  ({r['tamano_bytes']} bytes)"
            item = QListWidgetItem(texto)
            item.setData(Qt.ItemDataRole.UserRole, r["ruta"])
            self.lista_resultados.addItem(item)

    def _on_error(self, mensaje_error: str):
        self.boton_enviar.setEnabled(True)
        self._agregar_mensaje_chat("IA", f"⚠️ {mensaje_error}")

    def _abrir_ubicacion_seleccionada(self):
        items = self.lista_resultados.selectedItems()
        if not items:
            return
        ruta = items[0].data(Qt.ItemDataRole.UserRole)
        subprocess.run(["explorer", "/select,", ruta])

    def closeEvent(self, event):
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2)
        if self.indexador_thread and self.indexador_thread.isRunning():
            self.indexador_thread.terminate()
            self.indexador_thread.wait(2000)
        if self.consulta_thread and self.consulta_thread.isRunning():
            self.consulta_thread.terminate()
            self.consulta_thread.wait(2000)
        super().closeEvent(event)


def iniciar_gui():
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    iniciar_gui()
