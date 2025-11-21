from collections.abc import Iterable

from app.config.settings import Settings
from app.dominio.dtos import VideoAnaliticaDTO
from app.infra.ffmpeg_gateway import FFMPEFGateway
from app.infra.repositories import FilesystemRepository
from app.servicios.metricas_service import calcular_metricas_derivadas


def get_metricas(rutas: Iterable[str]) -> list[tuple[str, VideoAnaliticaDTO]]:
    """Dado un listado de rutas en texto, devolver sus metricas de video."""

    config = Settings.cargar_por_defecto()
    repository = FilesystemRepository(
        extensiones_permitidas=config.patrones_video,
        exclusiones=set(config.ruta_exclusiones or []),
    )

    mapeo_rutas = repository.mapear_paths(rutas)
    ffmpeg_gateway = FFMPEFGateway()
    resultados: list[tuple[str, VideoAnaliticaDTO]] = []

    for ruta_original, ruta_path in mapeo_rutas:
        if ruta_path is None:
            continue
        video_archivo = repository.construir_video_archivo(ruta_path)
        stream_video, streams_audio = ffmpeg_gateway.obtener_streams(video_archivo.ruta)
        video_analitica = VideoAnaliticaDTO(
            archivo=video_archivo,
            stream_video=stream_video,
            streams_audio=streams_audio,
        )
        resultados.append((ruta_original, video_analitica))

    calcular_metricas_derivadas([video for _, video in resultados])
    return resultados
