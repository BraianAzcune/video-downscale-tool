from __future__ import annotations

from pathlib import Path
from typing import Iterable
import sys
import subprocess
import os

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPalette, QColor
    from PySide6.QtWidgets import (
        QApplication,
        QFrame,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
    PYSIDE = True
except Exception:  # pragma: no cover - fallback to PyQt5 if available
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QPalette, QColor
    from PyQt5.QtWidgets import (
        QApplication,
        QFrame,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
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

        # Lista de archivos
        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_widget.setAlternatingRowColors(True)
        root.addWidget(self.list_widget, stretch=3)

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

    # Lógica
    def _on_dropped(self, paths: Iterable[str]) -> None:
        added = 0
        for p in paths:
            norm = str(Path(p).resolve())
            if norm in self._known:
                continue
            self._known.add(norm)
            item = QListWidgetItem(norm)
            self.list_widget.addItem(item)
            added += 1
        if added:
            self._update_counter()
            self._update_actions_enabled()

    def _update_counter(self) -> None:
        count = self.list_widget.count()
        self.count_label.setText(f"Total: {count}")

    def _update_actions_enabled(self) -> None:
        has_items = self.list_widget.count() > 0
        self.clear_btn.setEnabled(has_items)
        self.save_btn.setEnabled(has_items)

    def clear_list(self) -> None:
        self.list_widget.clear()
        self._known.clear()
        self._update_counter()
        self._update_actions_enabled()

    def save_list(self) -> None:
        if self.list_widget.count() == 0:
            return
        base_dir = Path(__file__).resolve().parent
        out_file = base_dir / "archivos_a_transformar.txt"
        try:
            with out_file.open("w", encoding="utf-8") as f:
                for i in range(self.list_widget.count()):
                    f.write(self.list_widget.item(i).text() + "\n")
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
            QListWidget { background: #111111; alternate-background-color: #151515; }
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
