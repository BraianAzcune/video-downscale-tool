
from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config.settings import Settings
from app.pipeline.workflow import ejecutar_pipeline
from logger_config import configurar_logging


def main():
    configurar_logging()
    base_dir = Path(__file__).resolve().parent.parent
    ruta_config = base_dir / "app" / "config" / "settings.txt"
    settings = Settings.cargar_desde_txt(ruta_config)
    ejecutar_pipeline(settings)

if __name__ == "__main__":
    main()
