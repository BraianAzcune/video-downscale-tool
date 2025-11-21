"""Helpers para generar previsualizaciones fijas de un video."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

import ffmpeg


@dataclass(frozen=True)
class PreviewFrame:
    """Representa una captura puntual del video."""

    timestamp: float
    image_path: Path


_DEFAULT_PREVIEWS_DIR = Path(__file__).resolve().parent / "previews"


def generar_previews_video(ruta_video: Path, carpeta_salida: Path | None = None) -> List[PreviewFrame]:
    """Generar tres capturas (3s, mitad, fin-4s) en la carpeta fija de previews."""
    carpeta_destino = _resolver_carpeta_salida(carpeta_salida)
    _limpiar_carpeta(carpeta_destino)

    ruta_normalizada = _validar_ruta(ruta_video)
    duracion_seg = _obtener_duracion_seg(ruta_normalizada)
    instantes = _resolver_instantes(duracion_seg)

    previews: List[PreviewFrame] = []
    for idx, instante in enumerate(instantes, start=1):
        nombre = f"{ruta_normalizada.stem}_preview_{idx}.jpg"
        destino_frame = carpeta_destino / nombre
        _extraer_frame(ruta_normalizada, instante, destino_frame)
        previews.append(PreviewFrame(timestamp=instante, image_path=destino_frame))
    return previews


def _resolver_carpeta_salida(carpeta_salida: Path | None) -> Path:
    if carpeta_salida is None:
        return _DEFAULT_PREVIEWS_DIR
    return Path(carpeta_salida).expanduser().resolve()


def _limpiar_carpeta(destino: Path) -> None:
    if destino.exists():
        if not destino.is_dir():
            raise NotADirectoryError(f"La ruta de previews no es un directorio: {destino}")
        shutil.rmtree(destino)
    destino.mkdir(parents=True, exist_ok=True)


def _validar_ruta(ruta_video: Path) -> Path:
    ruta = Path(ruta_video).expanduser().resolve()
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta_video}")
    if not ruta.is_file():
        raise FileNotFoundError(f"La ruta no es un archivo valido: {ruta_video}")
    return ruta


def _obtener_duracion_seg(ruta_video: Path) -> float:
    try:
        data = ffmpeg.probe(str(ruta_video))
    except ffmpeg.Error as exc:  # pragma: no cover
        stderr = exc.stderr.decode("utf-8", errors="ignore") if isinstance(exc.stderr, bytes) else exc.stderr
        raise RuntimeError(f"ffprobe fallo al obtener la duracion de '{ruta_video}': {stderr}") from exc
    duration_str = data.get("format", {}).get("duration")
    try:
        return float(duration_str)
    except (TypeError, ValueError):
        return 0.0


def _resolver_instantes(duracion_seg: float) -> Sequence[float]:
    if duracion_seg <= 0:
        return (0.0, 0.0, 0.0)

    limite = max(duracion_seg - 0.1, 0.0)
    inicio = 3.0 if duracion_seg >= 3.0 else max(duracion_seg * 0.2, 0.0)
    mitad = duracion_seg / 2.0
    antes_del_final = duracion_seg - 4.0 if duracion_seg > 4.0 else max(duracion_seg - 0.5, 0.0)

    def _clamp(valor: float) -> float:
        return max(0.0, min(valor, limite))

    instantes = (_clamp(inicio), _clamp(mitad), _clamp(antes_del_final))
    return instantes


def _extraer_frame(ruta_video: Path, timestamp: float, destino: Path) -> None:
    stream = (
        ffmpeg.input(str(ruta_video), ss=max(timestamp, 0.0))
        .output(str(destino), vframes=1, format="image2", vcodec="mjpeg")
        .global_args("-loglevel", "error")
        .overwrite_output()
    )
    try:
        stream.run(capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as exc:  # pragma: no cover
        stderr = exc.stderr.decode("utf-8", errors="ignore") if isinstance(exc.stderr, bytes) else exc.stderr
        raise RuntimeError(f"ffmpeg fallo al extraer preview en t={timestamp}s: {stderr}") from exc


if __name__ == "__main__":
    """Ejecuta este archivo directamente para probar la generacion de previews."""
    video_demo = Path(r"D:\songs\milet - Anytime Anywhere (Kan_Rom_Eng) Lyrics_歌詞.mp4")
    try:
        previews = generar_previews_video(video_demo)
    except Exception as exc:
        print(f"No se pudieron generar las previews para {video_demo}:\n  -> {exc}")
    else:
        print(f"Previews generadas para {video_demo}:")
        for frame in previews:
            print(f"  t={frame.timestamp:.2f}s -> {frame.image_path}")
