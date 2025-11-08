import logging
import os
from datetime import datetime


def configurar_logging():
    fecha_log = datetime.now().strftime("%Y%m%d-%H%M%S")
    carpeta_logs = "Logs"
    os.makedirs(carpeta_logs, exist_ok=True)

    log_file = os.path.join(carpeta_logs, f"{fecha_log}.log")

    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8",
    )
    logging.info("Logger configurado correctamente.")
