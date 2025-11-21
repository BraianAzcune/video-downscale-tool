"""Definiciones de DTOs que representan las entidades del dominio de métricas de video."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Literal


@dataclass
class VideoArchivoDTO:
    """Describe el archivo físico encontrado al escanear el filesystem."""
    ruta: Path
    size_bytes: int
    fecha_modificacion: datetime


@dataclass
class VideoStreamDTO:
    """Representa el flujo de video reportado por ffprobe con foco en compresión."""
    duracion_seg: float
    contenedor: str # mp4, mkv, mov, etc.
    codec: str
    bitrate_bps: Optional[int]
    bitrate_container_bps: Optional[int]
    width: int
    height: int
    fps: float
    pix_fmt: str
    profile: Optional[str]
    level: Optional[str]
    color_space: Optional[str]
    color_transfer: Optional[str]
    color_primaries: Optional[str]
    es_hdr: bool
    es_vfr: bool


@dataclass
class AudioStreamDTO:
    """Modela cada flujo de audio para estimar su aporte al peso total."""

    codec: str
    bitrate_bps: Optional[int]
    channels: int
    sample_rate: int
    layout: Optional[str]


@dataclass
class VideoAnaliticaDTO:
    """Unifica archivo, streams y métricas derivadas para el análisis principal."""
    # data extraida directamente de los archivos
    archivo: VideoArchivoDTO
    stream_video: VideoStreamDTO
    streams_audio: Optional[Sequence[AudioStreamDTO]] = None
    # campos calculados
    mb_por_minuto: Optional[float] = None
    bitrate_total_estimado: Optional[int] = None
    bits_por_pixel_frame: Optional[float] = None
    flags_contexto: Optional[List[FlagContexto]] = None
    # faclidad lectura
    kbps_total: Optional[int] = None
    kbps_video: Optional[int] = None
    audio_share_pct: Optional[float] = None 
    duracion_categoria: Optional[DuracionCategoria] = None
    # --- métricas condicionadas al bucket (post-agregado) ---
    bucket_resolucion_fps: Optional[str] = None
    ratio_vs_promedio_bucket: Optional[float] = None


DuracionCategoria = Literal["MUY CORTO", "CORTO", "MEDIO", "LARGO"]

FlagContexto = Literal[
    "OUTLIER_FUERTE",
    "OUTLIER_SUAVE",
    "MUY_CORTO",
    "DURACION_CORTA",
    "AUDIO_DOMINANTE",
    "VFR",
    "HDR",
    "BITRATE_CONTAINER_FALTANTE",
    "BUCKET_PEQUENO",
    "ESTIMACION_BITRATE",
]

@dataclass
class BucketResumenDTO:
    """Agregado por bucket resolución@fps con métricas estadísticas globales."""

    bucket_id: str
    promedio_mb_min: Optional[float]
    promedio_bitrate: Optional[int]
    videos_outliers: List[str] = field(default_factory=list)
    total_videos: int = 0
    desviacion_std_mb_min: Optional[float] = None
    mediana_mb_min: Optional[float] = None
    mad_mb_min: Optional[float] = None
