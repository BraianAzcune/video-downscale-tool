"""GUI para analizar rapidamente un video individual."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Garantizar que podamos importar el paquete principal `app`
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:  # pragma: no cover - fallback automatico
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QColor, QPixmap, QPalette, QDragEnterEvent, QDropEvent
    from PySide6.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QFrame,
        QLabel,
        QStackedLayout,
        QSizePolicy,
        QMainWindow,
        QMessageBox,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
        QHeaderView,
    )
except Exception:  # pragma: no cover
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QColor, QPixmap, QPalette, QDragEnterEvent, QDropEvent
    from PyQt5.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QLabel,
        QFrame,
        QStackedLayout,
        QSizePolicy,
        QMainWindow,
        QMessageBox,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
        QHeaderView,
    )

from app.dominio.dtos import VideoAnaliticaDTO, VideoArchivoDTO
from app.infra.ffmpeg_gateway import FFMPEFGateway
from app.servicios.metricas_service import calcular_metricas_derivadas

import evaluador
import previews

PreviewFrame = previews.PreviewFrame
generar_previews_video = previews.generar_previews_video
Evaluacion = evaluador.Evaluacion
evaluar_metricas = evaluador.evaluar_metricas


@dataclass
class VideoAnalysisResult:
    video: VideoAnaliticaDTO
    evaluaciones: Dict[str, Evaluacion]
    previews: List[PreviewFrame]
    preview_error: Optional[str] = None


METRIC_COLUMNS: List[tuple[str, str, Callable[[Optional[float]], str]]] = [
    ("mb_por_minuto", "MB/min", lambda v: "--" if v is None else f"{v:.2f} MB/min"),
    ("bits_por_pixel_frame", "bppf", lambda v: "--" if v is None else f"{v:.4f} bppf"),
    ("kbps_total", "kbps total", lambda v: "--" if v is None else f"{int(v)} kbps"),
    ("audio_share_pct", "% audio", lambda v: "--" if v is None else f"{v:.1f} %"),
    ("ratio_vs_promedio_bucket", "ratio bucket", lambda v: "--" if v is None else f"{v:.2f} x"),
]

FFMPEG_GATEWAY = FFMPEFGateway()


class DropPreviewArea(QFrame):
    """Area de drop que tambien muestra las previews."""

    def __init__(
        self,
        on_path: Callable[[Path], None],
        on_reset: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_path = on_path
        self._on_reset = on_reset
        self._stored_pixmap = QPixmap()
        self._current_tooltip = ""
        self._preview_active = False

        self.setAcceptDrops(True)
        self.setMinimumHeight(360)
        self.setObjectName("DropPreviewArea")
        self.setStyleSheet(
            """
            QFrame#DropPreviewArea {
                border: 2px dashed #1d4ed8;
                border-radius: 10px;
                background-color: #0b3d91;
            }
            QFrame#DropPreviewArea[dragActive="true"] {
                border-color: #60a5fa;
                background-color: #0a2a6a;
            }
            """
        )

        self.stack = QStackedLayout(self)
        self.stack.setContentsMargins(16, 16, 16, 16)
        self.stack.setSpacing(8)

        drop_container = QFrame(self)
        drop_layout = QVBoxLayout(drop_container)
        drop_layout.setContentsMargins(0, 0, 0, 0)
        drop_layout.setSpacing(8)

        self.message_label = QLabel("Arrastra un video aqui o haz click para seleccionar uno.")
        self.message_label.setAlignment(Qt.AlignCenter)
        font = self.message_label.font()
        font.setPointSize(font.pointSize() + 1)
        font.setBold(True)
        self.message_label.setFont(font)
        self.message_label.setWordWrap(True)

        drop_layout.addStretch(1)
        drop_layout.addWidget(self.message_label)
        drop_layout.addStretch(1)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_label.setMinimumHeight(360)
        self.preview_label.setStyleSheet("QLabel { background: transparent; }")

        self.stack.addWidget(drop_container)
        self.stack.addWidget(self.preview_label)
        self.stack.setCurrentWidget(drop_container)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if self._preview_active:
            event.ignore()
            return
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
        if self._preview_active:
            event.ignore()
            return
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        for url in urls:
            if url.isLocalFile():
                self._on_path(Path(url.toLocalFile()))
                event.acceptProposedAction()
                return
        event.ignore()

    def show_message(self, text: str) -> None:
        self._set_preview_active(False)
        self.message_label.setText(text)
        self._stored_pixmap = QPixmap()

    def set_preview_pixmap(self, pixmap: QPixmap, tooltip: str = "") -> None:
        self._stored_pixmap = pixmap
        self._current_tooltip = tooltip
        if pixmap.isNull():
            self.show_message("No se pudo mostrar la previsualizacion.")
            return
        self._activate_preview_mode()
        self._update_pixmap()

    def clear_preview(self) -> None:
        self.show_message("Arrastra un video aqui o suelta un archivo para analizarlo.")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self._preview_active:
            self._on_reset()
            event.accept()
            return
        return super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_pixmap()

    def _update_pixmap(self) -> None:
        if self._stored_pixmap.isNull() or not self.preview_label.isVisible():
            return
        scaled = self._stored_pixmap.scaled(
            self.preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)
        self.preview_label.setToolTip(self._current_tooltip)

    def _set_preview_active(self, active: bool) -> None:
        self._preview_active = active
        self.setAcceptDrops(not active)
        if active:
            self.stack.setCurrentWidget(self.preview_label)
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.preview_label.clear()
            self.stack.setCurrentIndex(0)
            self.setCursor(Qt.ArrowCursor)

    def _activate_preview_mode(self) -> None:
        self._set_preview_active(True)

    def _deactivate_preview_mode(self) -> None:
        self._set_preview_active(False)


def analizar_video(ruta: Path) -> VideoAnalysisResult:
    ruta = Path(ruta).expanduser().resolve()
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")
    if not ruta.is_file():
        raise FileNotFoundError(f"La ruta no es un archivo valido: {ruta}")

    stat = ruta.stat()
    archivo = VideoArchivoDTO(
        ruta=ruta,
        size_bytes=stat.st_size,
        fecha_modificacion=datetime.fromtimestamp(stat.st_mtime),
    )
    stream_video, streams_audio = FFMPEG_GATEWAY.obtener_streams(ruta)
    video = VideoAnaliticaDTO(
        archivo=archivo,
        stream_video=stream_video,
        streams_audio=streams_audio,
    )
    calcular_metricas_derivadas([video])

    metricas = {
        "mb_por_minuto": video.mb_por_minuto,
        "bits_por_pixel_frame": video.bits_por_pixel_frame,
        "kbps_total": video.kbps_total,
        "audio_share_pct": video.audio_share_pct,
        "ratio_vs_promedio_bucket": video.ratio_vs_promedio_bucket,
    }
    evaluaciones = evaluar_metricas(metricas, bucket_id=video.bucket_resolucion_fps)

    preview_error: Optional[str] = None
    try:
        previews_generadas = generar_previews_video(ruta)
    except Exception as exc:  # pragma: no cover - depende del entorno ffmpeg
        previews_generadas = []
        preview_error = str(exc)

    return VideoAnalysisResult(video=video, evaluaciones=evaluaciones, previews=previews_generadas, preview_error=preview_error)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Analizador de video")
        self.resize(980, 640)

        self.preview_frames: List[PreviewFrame] = []
        self.preview_index: int = 0
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(1500)
        self.preview_timer.timeout.connect(self._advance_preview)

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        self.path_label = QLabel("Archivo actual: (sin seleccionar)")
        self.path_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.path_label.setWordWrap(True)
        root.addWidget(self.path_label)

        self.drop_area = DropPreviewArea(self._on_path_dropped, self._reset_drop_area, self)
        root.addWidget(self.drop_area, stretch=3)

        self.table = QTableWidget(2, len(METRIC_COLUMNS), self)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(True)
        self.table.horizontalHeader().setVisible(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setVerticalHeaderLabels(["Recomendado", "Video actual"])
        self.table.setHorizontalHeaderLabels([col[1] for col in METRIC_COLUMNS])
        root.addWidget(self.table, stretch=2)

        self.current_result: Optional[VideoAnalysisResult] = None

    def _on_path_dropped(self, ruta: Path) -> None:
        self._analyze_path(ruta)

    def _analyze_path(self, ruta: Path) -> None:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        ruta_resuelta = ruta.expanduser().resolve()
        self.path_label.setText(f"Analizando: {ruta_resuelta}")
        self.drop_area.show_message("Procesando video…")
        try:
            result = analizar_video(ruta_resuelta)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo analizar el video:\n{exc}")
            self.drop_area.show_message("Error al analizar el video.")
        else:
            self.current_result = result
            self._render_result(result)
        finally:
            QApplication.restoreOverrideCursor()

    def _render_result(self, result: VideoAnalysisResult) -> None:
        video = result.video
        size_mb = video.archivo.size_bytes / (1024 * 1024)
        duracion = video.stream_video.duracion_seg or 0.0
        resolucion = f"{video.stream_video.width}x{video.stream_video.height}"
        fps = video.stream_video.fps
        bucket = video.bucket_resolucion_fps or "sin bucket"
        detalles = (
            f"{video.archivo.ruta}\n"
            f"{size_mb:.2f} MB · {duracion:.1f} s · {resolucion} @ {fps:.1f} fps · {bucket}"
        )
        if result.preview_error:
            detalles += f"\nPrevias no disponibles: {result.preview_error}"
        self.path_label.setText(detalles)

        self.preview_frames = result.previews
        self.preview_index = 0
        if self.preview_frames:
            self.preview_timer.start()
            self._set_preview_pixmap(self.preview_frames[0])
        else:
            self.preview_timer.stop()
            mensaje = "No hay previews disponibles."
            if result.preview_error:
                mensaje = f"No hay previews disponibles: {result.preview_error}"
            self.drop_area.show_message(mensaje)

        self._populate_table(result.evaluaciones)

    def _populate_table(self, evaluaciones: Dict[str, Evaluacion]) -> None:
        for col_idx, (clave, _, formatter) in enumerate(METRIC_COLUMNS):
            evaluacion = evaluaciones.get(clave)
            recomendado = evaluacion.recomendado if evaluacion else "--"
            valor = formatter(evaluacion.valor if evaluacion else None)

            item_rec = QTableWidgetItem(recomendado)
            item_rec.setTextAlignment(Qt.AlignCenter)
            item_rec.setBackground(QColor("#f5f5f5"))
            item_rec.setForeground(QColor("#0f0f0f"))
            self.table.setItem(0, col_idx, item_rec)

            item_val = QTableWidgetItem(valor)
            item_val.setTextAlignment(Qt.AlignCenter)
            if evaluacion is None or evaluacion.ok is None:
                bg = QColor("#4b5563")
            elif evaluacion.ok:
                bg = QColor("#1b5e20")
            else:
                bg = QColor("#7f1d1d")
            fg = QColor("#ffffff")
            item_val.setBackground(bg)
            item_val.setForeground(fg)
            tooltip = evaluacion.detalle if evaluacion else "Sin evaluacion"
            item_val.setToolTip(tooltip)
            self.table.setItem(1, col_idx, item_val)

    def _advance_preview(self) -> None:
        if not self.preview_frames:
            return
        self.preview_index = (self.preview_index + 1) % len(self.preview_frames)
        self._set_preview_pixmap(self.preview_frames[self.preview_index])

    def _set_preview_pixmap(self, frame: PreviewFrame) -> None:
        pixmap = QPixmap(str(frame.image_path))
        if pixmap.isNull():
            self.drop_area.show_message(f"Frame t={frame.timestamp:.2f}s no disponible.")
            return
        self.drop_area.set_preview_pixmap(pixmap, tooltip=f"t = {frame.timestamp:.2f} s")

    def _reset_drop_area(self) -> None:
        self.preview_timer.stop()
        self.preview_frames = []
        self.preview_index = 0
        self.current_result = None
        self.drop_area.clear_preview()
        self.path_label.setText("Archivo actual: (sin seleccionar)")


def _apply_dark_theme(app: QApplication) -> None:
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#000000"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#0f0f0f"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#151515"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#111111"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2563eb"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(
        """
        QWidget { background-color: #000000; color: #ffffff; }
        QTableWidget { gridline-color: #222222; }
        QPushButton {
            background: #111111; color: #ffffff; border: 1px solid #333333;
            padding: 6px 12px; border-radius: 4px;
        }
        QPushButton:hover { background: #1c1c1c; }
        QPushButton:pressed { background: #0f0f0f; }
        QComboBox, QLineEdit {
            background: #111111; border: 1px solid #333333; border-radius: 4px;
        }
        """
    )


def main() -> int:
    app = QApplication(sys.argv)
    _apply_dark_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
