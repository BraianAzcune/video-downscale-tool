import logging
import os
import time
from datetime import datetime


def configurar_logging() -> None:
    """Configurar logging basico a archivo con timestamp."""
    fecha_log = datetime.now().strftime("%Y%m%d-%H%M%S")
    carpeta_logs = "Logs"
    os.makedirs(carpeta_logs, exist_ok=True)

    log_file = os.path.join(carpeta_logs, f"{fecha_log}.log")

    handlers = [
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    # se quiere siempre, dejar comentado de momento # if os.getenv("EJECUTANDO_EN_VSCODE"):
    handlers.append(logging.StreamHandler()) # type: ignore

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )
    logging.info("Logger configurado correctamente.")


class ProgresoLogger:
    """Logger que reporta avances cada cierto intervalo o al terminar."""

    def __init__(self, titulo: str, total: int, intervalo_seg: float = 2.0) -> None:
        self._titulo = titulo
        self._total = total
        self._intervalo_seg = intervalo_seg
        self._ultimo_reporte = time.monotonic()

    def informar(self, cantidad: int) -> None:
        ahora = time.monotonic()
        if cantidad >= self._total or ahora - self._ultimo_reporte >= self._intervalo_seg:
            logging.info("%s %s/%s", self._titulo, cantidad, self._total)
            self._ultimo_reporte = ahora
