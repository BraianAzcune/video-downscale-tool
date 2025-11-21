from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.dominio.dtos import AudioStreamDTO, VideoAnaliticaDTO, VideoArchivoDTO, VideoStreamDTO
from app.servicios.metricas_service import (
    agrupar_en_buckets,
    calcular_bitrate_total_estimado,
    calcular_mb_por_minuto,
    calcular_metricas_bucket,
    calcular_metricas_derivadas,
    marcar_outliers,
)


def _build_video(
    size_bytes: int,
    duracion_seg: float,
    bitrate_container_bps: int | None = None,
    bitrate_video_bps: int | None = None,
    *,
    width: int = 640,
    height: int = 480,
    fps: float = 30.0,
    codec: str = "h264",
    es_hdr: bool = False,
    es_vfr: bool = False,
) -> VideoAnaliticaDTO:
    archivo = VideoArchivoDTO(
        ruta=Path("video.mp4"),
        size_bytes=size_bytes,
        fecha_modificacion=datetime(2024, 1, 1, 0, 0, 0),
    )
    stream_video = VideoStreamDTO(
        duracion_seg=duracion_seg,
        contenedor="mp4",
        codec=codec,
        bitrate_bps=bitrate_video_bps,
        bitrate_container_bps=bitrate_container_bps,
        width=width,
        height=height,
        fps=fps,
        pix_fmt="yuv420p",
        profile=None,
        level=None,
        color_space=None,
        color_transfer=None,
        color_primaries=None,
        es_hdr=es_hdr,
        es_vfr=es_vfr,
    )
    return VideoAnaliticaDTO(archivo=archivo, stream_video=stream_video)


def test_calcular_mb_por_minuto_devuelve_ratio_correcto() -> None:
    size_bytes = 10 * 1024 * 1024
    duracion = 120.0

    resultado = calcular_mb_por_minuto(size_bytes=size_bytes, duracion_seg=duracion)

    assert resultado == pytest.approx(5.0) # type: ignore


def test_calcular_mb_por_minuto_con_datos_invalidos_devuelve_none() -> None:
    assert calcular_mb_por_minuto(size_bytes=1024, duracion_seg=0) is None
    assert calcular_mb_por_minuto(size_bytes=0, duracion_seg=10) is None
    assert calcular_mb_por_minuto(size_bytes=2048, duracion_seg=None) is None


def test_calcular_metricas_derivadas_actualiza_dto() -> None:
    archivo = VideoArchivoDTO(
        ruta=Path(r"D:\songs\milet - Anytime Anywhere (Kan_Rom_Eng) Lyrics_歌詞.mp4"),
        size_bytes=8_053_740,
        fecha_modificacion=datetime(2025, 11, 8, 15, 23, 26, 716782),
    )
    stream_video = VideoStreamDTO(
        duracion_seg=230.533333,
        contenedor="mov,mp4,m4a,3gp,3g2,mj2",
        codec="h264",
        bitrate_bps=142_733,
        bitrate_container_bps=279_460,
        width=854,
        height=480,
        fps=30.0,
        pix_fmt="yuv420p",
        profile="Main",
        level="31",
        color_space="bt709",
        color_transfer="bt709",
        color_primaries="bt709",
        es_hdr=False,
        es_vfr=False,
    )
    streams_audio = [
        AudioStreamDTO(
            codec="aac",
            bitrate_bps=128_001,
            channels=2,
            sample_rate=44_100,
            layout="stereo",
        )
    ]
    video = VideoAnaliticaDTO(archivo=archivo, stream_video=stream_video, streams_audio=streams_audio)

    calcular_metricas_derivadas([video])

    assert video.mb_por_minuto == pytest.approx(1.9990111336342857)  # type: ignore
    assert video.bitrate_total_estimado == 279_460
    assert video.duracion_categoria == "MEDIO"
    assert video.flags_contexto is None
    assert video.bits_por_pixel_frame == pytest.approx(0.01161, rel=1e-4)  # type: ignore
    assert video.kbps_total == 279
    assert video.kbps_video == 143
    assert video.audio_share_pct == pytest.approx(45.80297717025692, rel=1e-6)  # type: ignore




def test_calcular_metricas_derivadas_asigna_bucket_y_flags_hdr_vfr() -> None:
    video = _build_video(
        size_bytes=12 * 1024 * 1024,
        duracion_seg=120.0,
        bitrate_container_bps=450_000,
        bitrate_video_bps=400_000,
        width=1920,
        height=1080,
        fps=59.94,
        codec="hevc",
        es_hdr=True,
        es_vfr=True,
    )

    calcular_metricas_derivadas([video])

    assert video.bucket_resolucion_fps == "1080p@60/HDR/HEVC"
    flags = set(video.flags_contexto or [])
    assert {"HDR", "VFR"} <= flags


def test_calcular_metricas_bucket_calcula_estadisticos() -> None:
    videos = [
        _build_video(size_bytes=6 * 1024 * 1024, duracion_seg=180.0, bitrate_container_bps=200_000),
        _build_video(size_bytes=9 * 1024 * 1024, duracion_seg=180.0, bitrate_container_bps=300_000),
        _build_video(size_bytes=12 * 1024 * 1024, duracion_seg=180.0, bitrate_container_bps=400_000),
    ]

    calcular_metricas_derivadas(videos)
    buckets = agrupar_en_buckets(videos)
    assert len(buckets) == 1
    bucket_id, agrupados = next(iter(buckets.items()))

    resumen = calcular_metricas_bucket(bucket_id, agrupados)

    assert resumen.total_videos == 3
    assert resumen.promedio_mb_min == pytest.approx(3.0)
    assert resumen.desviacion_std_mb_min == pytest.approx(0.81649658, rel=1e-6)
    assert resumen.mediana_mb_min == pytest.approx(3.0)
    assert resumen.mad_mb_min == pytest.approx(1.0)
    assert resumen.promedio_bitrate == 300_000


def test_marcar_outliers_aplica_ratio_y_flags() -> None:
    videos = [
        _build_video(size_bytes=6 * 1024 * 1024, duracion_seg=180.0, bitrate_container_bps=250_000)
        for _ in range(5)
    ]

    calcular_metricas_derivadas(videos)
    valores_mb = [2.0, 3.0, 3.0, 6.0, 9.0]
    for video, valor in zip(videos, valores_mb):
        video.mb_por_minuto = valor

    buckets = agrupar_en_buckets(videos)
    bucket_id, agrupados = next(iter(buckets.items()))
    resumen = calcular_metricas_bucket(bucket_id, agrupados)
    umbrales = {"mb_por_minuto": {"outlier_suave": 2.0, "outlier_fuerte": 3.0}, "min_bucket": 5}

    marcar_outliers(agrupados, resumen, umbrales)

    assert agrupados[-1].ratio_vs_promedio_bucket == pytest.approx(3.0)
    flags_suave = set(agrupados[-2].flags_contexto or [])
    flags_fuerte = set(agrupados[-1].flags_contexto or [])

    assert "OUTLIER_SUAVE" in flags_suave
    assert "OUTLIER_FUERTE" not in flags_suave
    assert "OUTLIER_FUERTE" in flags_fuerte
    assert "BUCKET_PEQUENO" not in flags_fuerte
    assert len(resumen.videos_outliers) == 2

def test_calcular_metricas_derivadas_agrega_flags_muy_corto_y_estimacion() -> None:
    video = _build_video(size_bytes=5 * 1024 * 1024, duracion_seg=5.0)

    calcular_metricas_derivadas([video])

    assert video.duracion_categoria == "MUY CORTO"
    assert set(video.flags_contexto or []) >= {"MUY_CORTO", "BITRATE_CONTAINER_FALTANTE", "ESTIMACION_BITRATE"}


def test_calcular_metricas_derivadas_agrega_flag_duracion_corta_y_bitrate_container() -> None:
    video = _build_video(
        size_bytes=10 * 1024 * 1024,
        duracion_seg=20.0,
        bitrate_video_bps=200_000,
    )

    calcular_metricas_derivadas([video])

    flags = set(video.flags_contexto or [])
    assert video.duracion_categoria == "CORTO"
    assert "DURACION_CORTA" in flags
    assert "MUY_CORTO" not in flags
    assert "BITRATE_CONTAINER_FALTANTE" in flags
    assert "ESTIMACION_BITRATE" not in flags


def test_calcular_bitrate_total_estimado_prefiere_format() -> None:
    resultado, fuente = calcular_bitrate_total_estimado(
        bitrate_container_bps=300_000,
        bitrate_video_bps=100_000,
        streams_audio=[
            AudioStreamDTO(codec="aac", bitrate_bps=64_000, channels=2, sample_rate=44_100, layout=None)
        ],
        size_bytes=0,
        duracion_seg=None,
    )

    assert resultado == 300_000
    assert fuente == "format"


def test_calcular_bitrate_total_estimado_suma_componentes() -> None:
    resultado, fuente = calcular_bitrate_total_estimado(
        bitrate_container_bps=None,
        bitrate_video_bps=200_000,
        streams_audio=[
            AudioStreamDTO(codec="aac", bitrate_bps=64_000, channels=2, sample_rate=44_100, layout=None),
            AudioStreamDTO(codec="aac", bitrate_bps=None, channels=2, sample_rate=48_000, layout=None),
        ],
        size_bytes=0,
        duracion_seg=120.0,
    )

    assert resultado == 264_000
    assert fuente == "componentes"


def test_calcular_bitrate_total_estimado_estima_por_tamano_tiempo() -> None:
    size_bytes = 8 * 1024 * 1024  # 8 MB
    resultado, fuente = calcular_bitrate_total_estimado(
        bitrate_container_bps=None,
        bitrate_video_bps=None,
        streams_audio=[],
        size_bytes=size_bytes,
        duracion_seg=64.0,
    )

    assert resultado == pytest.approx(int((size_bytes * 8) / 64.0)) # type: ignore
    assert fuente == "tamano"


def test_calcular_bitrate_total_estimado_sin_datos() -> None:
    resultado, fuente = calcular_bitrate_total_estimado(
        bitrate_container_bps=None,
        bitrate_video_bps=None,
        streams_audio=None,
        size_bytes=0,
        duracion_seg=0.0,
    )

    assert resultado is None
    assert fuente == "none"
