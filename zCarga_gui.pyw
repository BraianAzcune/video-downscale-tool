from __future__ import annotations

from pathlib import Path
from typing import Iterable, Any
import sys
import subprocess
import os
import threading

# Habilitar importaciones del subproyecto metricas-videos
_BASE_DIR = Path(__file__).resolve().parent
_METRICAS_DIR = _BASE_DIR / "metricas-videos"
if str(_METRICAS_DIR) not in sys.path:
    sys.path.insert(0, str(_METRICAS_DIR))

from app.pipeline.get_metricas import get_metricas  # type: ignore

try:
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPalette, QColor
    from PySide6.QtWidgets import (
        QApplication,
        QFrame,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtWidgets import QHeaderView
    SignalType = Signal
    PYSIDE = True
except Exception:  # pragma: no cover - fallback to PyQt5 if available
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal
    from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QPalette, QColor
    from PyQt5.QtWidgets import (
        QApplication,
        QFrame,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    from PyQt5.QtWidgets import QHeaderView
    SignalType = pyqtSignal
    PYSIDE = False


class DropArea(QFrame):
    def __init__(self, on_paths: callable[[Iterable[str]], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._on_paths = on_paths

        self.setObjectName("DropArea")
        self.setStyleSheet(
            """
            QFrame#DropArea {
                border: 2px dashed #1d4ed8; /* azul */
                border-radius: 8px;
                color: #ffffff;
                background: #0b3d91;      /* azul oscuro */
            }
            QFrame#DropArea[dragActive="true"] {
                border-color: #60a5fa;    /* azul claro */
                background: #0a2a6a;      /* mas oscuro al arrastrar */
                color: #ffffff;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel("Arrastra aquí archivos o carpetas")
        subtitle = QLabel("Suelta para agregarlos a la lista")
        title.setAlignment(Qt.AlignCenter)
        subtitle.setAlignment(Qt.AlignCenter)

        font = title.font()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        title.setFont(font)

        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(1)

    # Qt drag & drop events
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)

        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        paths: list[str] = []
        for url in urls:
            if url.isLocalFile():
                paths.append(url.toLocalFile())
            else:
                # Para rutas no locales, conservamos la representación de texto
                paths.append(url.toString())
        self._on_paths(paths)
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    kbps_ready = SignalType(list, list, object)  # resultados, rutas_pendientes, exc

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("zCarga - Arrastrar y Guardar")
        self.resize(720, 480)

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Área de drop
        self.drop_area = DropArea(self._on_dropped, self)
        root.addWidget(self.drop_area, stretch=2)

        # Tabla de archivos
        self.table = QTableWidget(0, 2, self)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(["Ruta", "Kbps total"])
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        root.addWidget(self.table, stretch=3)

        # Barra inferior con contador y acciones
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.count_label = QLabel("Total: 0")
        bottom.addWidget(self.count_label)
        bottom.addStretch(1)

        self.clear_btn = QPushButton("Limpiar")
        self.save_btn = QPushButton("Guardar y ejecutar")
        try:
            self.clear_btn.clicked.disconnect()
        except Exception:
            pass
        self.clear_btn.clicked.connect(self.clear_list)  # type: ignore[arg-type]
        try:
            self.save_btn.clicked.disconnect()
        except Exception:
            pass
        self.save_btn.clicked.connect(self.save_list)  # type: ignore[arg-type]
        self._update_actions_enabled()
        bottom.addWidget(self.clear_btn)
        bottom.addWidget(self.save_btn)

        root.addLayout(bottom)

        # Conjunto interno para evitar duplicados
        self._known: set[str] = set()
        self._spawn_guard: bool = False
        self._pending_paths: set[str] = set()
        self._kbps_worker_running: bool = False
        self._spinner_frames = ["|", "/", "-", "\\"]
        self._spinner_index = 0
        self._spinner_timer: QTimer | None = None
        self.kbps_ready.connect(self._on_kbps_ready)  # type: ignore[arg-type]

    # Lógica
    def _on_dropped(self, paths: Iterable[str]) -> None:
        added = 0
        nuevos: list[str] = []
        for p in paths:
            norm = str(Path(p).resolve())
            if norm in self._known:
                continue
            self._known.add(norm)
            row = self.table.rowCount()
            self.table.insertRow(row)
            path_item = QTableWidgetItem(norm)
            kbps_item = QTableWidgetItem("-")
            kbps_item.setTextAlignment(Qt.AlignCenter)
            path_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            kbps_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(row, 0, path_item)
            self.table.setItem(row, 1, kbps_item)
            added += 1
            nuevos.append(norm)
        if added:
            self._update_counter()
            self._update_actions_enabled()
            self._mark_pending(nuevos)
            self._start_kbps_worker()

    def _update_counter(self) -> None:
        count = self.table.rowCount()
        self.count_label.setText(f"Total: {count}")

    def _update_actions_enabled(self) -> None:
        has_items = self.table.rowCount() > 0
        self.clear_btn.setEnabled(has_items)
        self.save_btn.setEnabled(has_items)

    def clear_list(self) -> None:
        self.table.setRowCount(0)
        self._known.clear()
        self._pending_paths.clear()
        self._update_counter()
        self._update_actions_enabled()
        self._clear_kbps()

    def save_list(self) -> None:
        if self.table.rowCount() == 0:
            return
        base_dir = Path(__file__).resolve().parent
        out_file = base_dir / "archivos_a_transformar.txt"
        try:
            with out_file.open("w", encoding="utf-8") as f:
                for i in range(self.table.rowCount()):
                    item = self.table.item(i, 0)
                    if item:
                        f.write(item.text() + "\n")
        except OSError as exc:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el archivo:\n{exc}")
            return
        # Lanzar proceso independiente tras guardar (una sola vez por click).
        if self._spawn_guard:
            return
        self._spawn_guard = True
        self._launch_processor()
        # Resetear guard en el siguiente tick para evitar disparos múltiples en el mismo evento
        QTimer.singleShot(50, lambda: setattr(self, "_spawn_guard", False))

    def _launch_processor(self) -> None:
        base_dir = Path(__file__).resolve().parent
        script = str(base_dir / "procesar_videos.py")
        try:
            if os.name == "nt":
                # Ejecutar con la asociación de Windows (igual que doble click)
                os.startfile(script)  # type: ignore[attr-defined]
            else:
                # En otros SO, lanzarlo normalmente con intérprete
                subprocess.Popen([sys.executable, script], cwd=str(base_dir))
        except Exception as exc:
            # Solo mostramos error si falla el arranque del proceso
            QMessageBox.critical(self, "Error", f"No se pudo iniciar el proceso:\n{exc}")

    def _start_spinner(self) -> None:
        if self._spinner_timer is None:
            self._spinner_timer = QTimer(self)
            self._spinner_timer.timeout.connect(self._tick_spinner)  # type: ignore[arg-type]
        if not self._spinner_timer.isActive():
            self._spinner_timer.start(120)

    def _stop_spinner_if_idle(self) -> None:
        if self._spinner_timer and not self._pending_paths:
            self._spinner_timer.stop()

    def _tick_spinner(self) -> None:
        if not self._pending_paths:
            self._stop_spinner_if_idle()
            return
        self._spinner_index = (self._spinner_index + 1) % len(self._spinner_frames)
        frame = self._spinner_frames[self._spinner_index]
        for i in range(self.table.rowCount()):
            ruta_item = self.table.item(i, 0)
            kbps_item = self.table.item(i, 1)
            if not ruta_item or not kbps_item:
                continue
            if ruta_item.text() in self._pending_paths:
                kbps_item.setText(frame)

    def _mark_pending(self, paths: Iterable[str]) -> None:
        for ruta in paths:
            norm = str(Path(ruta).resolve())
            self._pending_paths.add(norm)
            # Mostrar frame inicial del spinner en la fila correspondiente
            for i in range(self.table.rowCount()):
                ruta_item = self.table.item(i, 0)
                kbps_item = self.table.item(i, 1)
                if ruta_item and kbps_item and ruta_item.text() == norm:
                    kbps_item.setText(self._spinner_frames[self._spinner_index])
        self._start_spinner()

    def _start_kbps_worker(self) -> None:
        if self._kbps_worker_running or not self._pending_paths:
            return

        rutas_pendientes = list(self._pending_paths)
        self._kbps_worker_running = True

        def worker() -> None:
            exc: Exception | None = None
            resultados: list[tuple[str, "VideoAnaliticaDTO"]] = []
            try:
                resultados = get_metricas(rutas_pendientes)
            except Exception as e:  # pragma: no cover - UI feedback
                exc = e

            # Pasar el resultado al hilo de UI
            self.kbps_ready.emit(resultados, rutas_pendientes, exc)

        threading.Thread(target=worker, daemon=True).start()

    def _set_kbps_value(self, ruta: str, valor: int | None) -> None:
        objetivo = ruta
        for i in range(self.table.rowCount()):
            ruta_item = self.table.item(i, 0)
            kbps_item = self.table.item(i, 1)
            if ruta_item and kbps_item and ruta_item.text() == objetivo:
                kbps_item.setText(str(valor) if valor is not None else "-")

    def _on_kbps_ready(
        self,
        resultados: list[tuple[str, Any]],
        rutas_pendientes: list[str],
        exc: Exception | None,
    ) -> None:
        self._kbps_worker_running = False
        if exc:
            QMessageBox.warning(self, "Error al calcular metricas", str(exc))
            for ruta in rutas_pendientes:
                self._set_kbps_value(ruta, None)
            self._pending_paths.difference_update(rutas_pendientes)
            self._stop_spinner_if_idle()
            self._start_kbps_worker()
            return

        kbps_por_ruta = {
            ruta: video.kbps_total for ruta, video in resultados
        }
        for ruta in rutas_pendientes:
            valor = kbps_por_ruta.get(ruta)
            self._set_kbps_value(ruta, valor)
        self._pending_paths.difference_update(rutas_pendientes)
        self._stop_spinner_if_idle()
        self._start_kbps_worker()

    def _clear_kbps(self) -> None:
        """Resetear la columna Kbps a vacio."""

        for i in range(self.table.rowCount()):
            kbps_item = self.table.item(i, 1)
            if kbps_item:
                kbps_item.setText("-")
        self._stop_spinner_if_idle()


def main() -> int:
    import sys

    app = QApplication(sys.argv)

    # Tema oscuro global: fondo negro, texto blanco, acentos azules
    def apply_dark_theme(a: QApplication) -> None:
        palette = a.palette()
        palette.setColor(QPalette.Window, QColor("#000000"))
        palette.setColor(QPalette.WindowText, QColor("#ffffff"))
        palette.setColor(QPalette.Base, QColor("#111111"))
        palette.setColor(QPalette.AlternateBase, QColor("#151515"))
        palette.setColor(QPalette.Text, QColor("#ffffff"))
        palette.setColor(QPalette.Button, QColor("#111111"))
        palette.setColor(QPalette.ButtonText, QColor("#ffffff"))
        palette.setColor(QPalette.BrightText, QColor("#ffffff"))
        palette.setColor(QPalette.Highlight, QColor("#0b3d91"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        a.setPalette(palette)

        a.setStyleSheet(
            """
            QWidget { background-color: #000000; color: #ffffff; }
            QListWidget, QTableWidget {
                background: #111111;
                alternate-background-color: #151515;
                gridline-color: #333333;
            }
            QHeaderView::section {
                background-color: #0f0f0f;
                color: #ffffff;
                border: 1px solid #333333;
                padding: 4px 6px;
            }
            QPushButton {
                background: #111111; color: #ffffff; border: 1px solid #333333;
                padding: 6px 12px; border-radius: 4px;
            }
            QPushButton:hover { background: #1a1a1a; }
            QPushButton:pressed { background: #0f0f0f; }
            QToolTip { color: #ffffff; background-color: #111111; border: 1px solid #333333; }
            """
        )

    apply_dark_theme(app)

    # Ocultar consola al ejecutar en Windows (doble click)
    if sys.platform.startswith("win"):
        try:
            import ctypes  # type: ignore
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
                ctypes.windll.kernel32.FreeConsole()
        except Exception:
            pass

    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
