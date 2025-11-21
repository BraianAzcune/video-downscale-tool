from pathlib import Path

from app.config.settings import Settings


def test_cargar_desde_txt_lee_settings_txt():
    base_dir = Path(__file__).resolve().parent.parent
    ruta_config = base_dir / "app" / "config" / "settings.txt"

    settings = Settings.cargar_desde_txt(ruta_config)

    # ruta_debug en settings.txt debe prevalecer sobre raiz_media.
    assert settings.raiz_media == Path(r"D:\songs")
    assert settings.output_excel == Path(r"C:\Users\braia\Downloads\metricas_videos.xlsx")
    assert settings.patrones_video[:3] == [".mp4", ".m4v", ".mov"]
    assert settings.ruta_exclusiones is not None
    assert settings.ruta_exclusiones[-1] == Path(r"D:\OBS-RECORDS\presa facil.mp4")
