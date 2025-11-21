"""Orquestador principal del pipeline de metricas de video."""
from __future__ import annotations

from app.config.settings import Settings
from app.dominio.dtos import BucketResumenDTO, VideoAnaliticaDTO
from app.infra.ffmpeg_gateway import FFMPEFGateway
from app.infra.repositories import FilesystemRepository
from app.servicios.crawler_service import buscar_videos_en_arbol
from app.servicios.excel_service import generar_excel_resumen
from app.servicios.metricas_service import (
    UmbralesOutliers,
    agrupar_en_buckets,
    calcular_metricas_bucket,
    calcular_metricas_derivadas,
    marcar_outliers,
)
from app.servicios.rutas_service import resolver_destino_con_timestamp
from logger_config import ProgresoLogger


def ejecutar_pipeline(config: Settings) -> None:
    """Secuencia principal para recolectar, procesar y exportar metricas."""
    # 1. Preparar repositories y gateway segun la configuracion.
    repository = FilesystemRepository(
        extensiones_permitidas=config.patrones_video,
        exclusiones=set(config.ruta_exclusiones or []),
    )
    # 2. Buscar los videos aplicando exclusiones.
    lista_videos = buscar_videos_en_arbol(config.raiz_media, repository=repository)
    # 3. Construir DTOs con metadata basica y tecnica.
    ffmpeg_gateway = FFMPEFGateway()
    videos_analitica: list[VideoAnaliticaDTO] = []
    progress_logger = ProgresoLogger("FFprobe progreso", len(lista_videos))

    for procesados, video in enumerate(lista_videos, start=1):
        stream_video, streams_audio = ffmpeg_gateway.obtener_streams(video.ruta)
        videos_analitica.append(
            VideoAnaliticaDTO(
                archivo=video,
                stream_video=stream_video,
                streams_audio=streams_audio,
            )
        )
        progress_logger.informar(procesados)
    # 4. Calcular metricas derivadas y agrupar en buckets.
    calcular_metricas_derivadas(videos_analitica)
    buckets = agrupar_en_buckets(videos_analitica)
    bucket_resumenes: dict[str, BucketResumenDTO] = {}
    umbrales_outliers: UmbralesOutliers = {
        "mb_por_minuto": {"outlier_suave": 2.0, "outlier_fuerte": 3.0},
        "min_bucket": 5,
    }
    # 5. Marcar outliers
    for bucket_id, bucket_videos in buckets.items():
        resumen = calcular_metricas_bucket(bucket_id, bucket_videos)
        bucket_resumenes[bucket_id] = resumen
        marcar_outliers(bucket_videos, resumen, umbrales_outliers)
    # debug_print({"videos": videos_analitica, "buckets": bucket_resumenes, "excel": config.output_excel})
    # 6. Exportar resultados a Excel.
    destino_excel = resolver_destino_con_timestamp(config.output_excel, config.raiz_media)
    generar_excel_resumen(destino_excel, videos_analitica, bucket_resumenes)
