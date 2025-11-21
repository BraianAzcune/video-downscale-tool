"""Servicio que agrupa videos y marca outliers segun metricas definidas."""
from __future__ import annotations

from math import sqrt
from typing import Dict, List, Optional, Sequence, Tuple, Literal, TypedDict

from app.dominio.dtos import AudioStreamDTO, BucketResumenDTO, DuracionCategoria, VideoAnaliticaDTO, FlagContexto

_BYTES_POR_MB = 1024 * 1024
_SEGUNDOS_POR_MINUTO = 60
_BITS_POR_BYTE = 8
_RESOLUCIONES_NORMALIZADAS = (144, 240, 360, 480, 720, 1080, 1440, 2160, 4320)
_FPS_NORMALIZADOS = (24, 25, 30, 50, 60)
_MAD_FACTOR = 1.4826
_MIN_BUCKET_CONFIABLE = 5
_BUCKET_DESCONOCIDO = "SIN_CLASIFICACION"
BitrateFuente = Literal["format", "componentes", "tamano", "none"]


class UmbralDetalle(TypedDict):
    outlier_suave: float
    outlier_fuerte: float


class UmbralesOutliers(TypedDict, total=False):
    mb_por_minuto: UmbralDetalle
    min_bucket: int


def calcular_metricas_derivadas(videos: List[VideoAnaliticaDTO]) -> List[VideoAnaliticaDTO]:
    """Calcular y asignar metricas derivadas disponibles para cada video."""
    for video in videos:
        video.mb_por_minuto = calcular_mb_por_minuto(
            size_bytes=video.archivo.size_bytes,
            duracion_seg=video.stream_video.duracion_seg,
        )
        _aplicar_contexto_duracion(video)
        bitrate_total, fuente = calcular_bitrate_total_estimado(
            bitrate_container_bps=video.stream_video.bitrate_container_bps,
            bitrate_video_bps=video.stream_video.bitrate_bps,
            streams_audio=video.streams_audio,
            size_bytes=video.archivo.size_bytes,
            duracion_seg=video.stream_video.duracion_seg,
        )
        video.bitrate_total_estimado = bitrate_total
        _actualizar_flags_bitrate(video, fuente)
        if video.stream_video.es_vfr:
            _agregar_flag(video, "VFR")
        if video.stream_video.es_hdr:
            _agregar_flag(video, "HDR")
        video.bits_por_pixel_frame = _calcular_bits_por_pixel_frame(
            bitrate_video_bps=video.stream_video.bitrate_bps,
            width=video.stream_video.width,
            height=video.stream_video.height,
            fps=video.stream_video.fps,
        )
        video.kbps_total = _calcular_kbps(video.bitrate_total_estimado)
        video.kbps_video = _calcular_kbps(video.stream_video.bitrate_bps)
        video.audio_share_pct = _calcular_audio_share_pct(
            streams_audio=video.streams_audio,
            bitrate_total=video.bitrate_total_estimado,
        )
        video.bucket_resolucion_fps = _resolver_bucket_resolucion(video)
    return videos


def calcular_mb_por_minuto(size_bytes: int, duracion_seg: Optional[float]) -> Optional[float]:
    """Retornar el ratio de megabytes por minuto usando tamano y duracion del video."""
    if size_bytes <= 0:
        return None
    if duracion_seg is None or duracion_seg <= 0:
        return None
    minutos = duracion_seg / _SEGUNDOS_POR_MINUTO
    if minutos <= 0:
        return None
    megabytes = size_bytes / _BYTES_POR_MB
    return megabytes / minutos


def calcular_bitrate_total_estimado(
    *,
    bitrate_container_bps: Optional[int],
    bitrate_video_bps: Optional[int],
    streams_audio: Optional[Sequence[AudioStreamDTO]],
    size_bytes: int,
    duracion_seg: Optional[float],
) -> Tuple[Optional[int], BitrateFuente]:
    """Estimar el bitrate total siguiendo el orden recomendado en la documentacion."""
    if bitrate_container_bps and bitrate_container_bps > 0:
        return bitrate_container_bps, "format"

    componentes: list[int] = []
    if bitrate_video_bps and bitrate_video_bps > 0:
        componentes.append(bitrate_video_bps)
    if streams_audio:
        for stream_audio in streams_audio:
            if stream_audio.bitrate_bps and stream_audio.bitrate_bps > 0:
                componentes.append(stream_audio.bitrate_bps)

    if componentes:
        return sum(componentes), "componentes"

    if size_bytes > 0 and duracion_seg and duracion_seg > 0:
        estimado = int((size_bytes * _BITS_POR_BYTE) / duracion_seg)
        return estimado, "tamano"

    return None, "none"


def _aplicar_contexto_duracion(video: VideoAnaliticaDTO) -> None:
    """Clasificar duracion y marcar flags de contexto para clips cortos."""
    duracion = video.stream_video.duracion_seg
    video.duracion_categoria = _calcular_duracion_categoria(duracion)
    if duracion <= 0:
        return
    if duracion < 10:
        _agregar_flag(video, "MUY_CORTO")
    elif duracion < 30:
        _agregar_flag(video, "DURACION_CORTA")


def _calcular_duracion_categoria(duracion_seg: float) -> DuracionCategoria:
    if duracion_seg < 10:
        return "MUY CORTO"
    if duracion_seg <= 120:
        return "CORTO"
    if duracion_seg <= 300:
        return "MEDIO"
    return "LARGO"


def _calcular_bits_por_pixel_frame(
    *,
    bitrate_video_bps: Optional[int],
    width: int,
    height: int,
    fps: float,
) -> Optional[float]:
    if not bitrate_video_bps or bitrate_video_bps <= 0:
        return None
    if width <= 0 or height <= 0 or fps <= 0:
        return None
    denominador = width * height * fps
    if denominador <= 0:
        return None
    return round(bitrate_video_bps / denominador, 5)


def _calcular_kbps(valor_bps: Optional[int]) -> Optional[int]:
    if not valor_bps or valor_bps <= 0:
        return None
    return round(valor_bps / 1000)


def _calcular_audio_share_pct(
    *,
    streams_audio: Optional[Sequence[AudioStreamDTO]],
    bitrate_total: Optional[int],
) -> Optional[float]:
    if not bitrate_total or bitrate_total <= 0 or not streams_audio:
        return None
    aporte_audio = sum(
        stream.bitrate_bps
        for stream in streams_audio
        if stream.bitrate_bps and stream.bitrate_bps > 0
    )
    if aporte_audio <= 0:
        return None
    return 100 * (aporte_audio / bitrate_total)


def _resolver_bucket_resolucion(video: VideoAnaliticaDTO) -> Optional[str]:
    altura = _normalizar_altura(video.stream_video.height)
    fps = _normalizar_fps(video.stream_video.fps)
    if altura is None or fps is None:
        return None
    codec = (video.stream_video.codec or "UNKNOWN").upper()
    bucket = f"{altura}p@{fps}"
    if video.stream_video.es_hdr:
        bucket = f"{bucket}/HDR"
    bucket = f"{bucket}/{codec}"
    return bucket


def _normalizar_altura(height: int) -> Optional[int]:
    if height <= 0:
        return None
    return min(_RESOLUCIONES_NORMALIZADAS, key=lambda objetivo: abs(objetivo - height))


def _normalizar_fps(fps: float) -> Optional[int]:
    if not fps or fps <= 0:
        return None
    return min(_FPS_NORMALIZADOS, key=lambda objetivo: abs(objetivo - fps))


def _promedio(valores: Sequence[float]) -> Optional[float]:
    if not valores:
        return None
    return float(sum(valores)) / len(valores)


def _desviacion_std(valores: Sequence[float]) -> Optional[float]:
    if len(valores) < 2:
        return None
    promedio = _promedio(valores)
    if promedio is None:
        return None
    varianza = sum((valor - promedio) ** 2 for valor in valores) / len(valores)
    return sqrt(varianza)


def _mediana(valores: Sequence[float]) -> Optional[float]:
    if not valores:
        return None
    ordenados = sorted(valores)
    mitad = len(ordenados) // 2
    if len(ordenados) % 2 == 1:
        return ordenados[mitad]
    return (ordenados[mitad - 1] + ordenados[mitad]) / 2


def _mad(valores: Sequence[float], mediana: Optional[float]) -> Optional[float]:
    if not valores or mediana is None:
        return None
    desviaciones = [abs(valor - mediana) for valor in valores]
    return _mediana(desviaciones)


def _actualizar_flags_bitrate(video: VideoAnaliticaDTO, fuente: BitrateFuente) -> None:
    if fuente in {"componentes", "tamano", "none"}:
        _agregar_flag(video, "BITRATE_CONTAINER_FALTANTE")
    if fuente == "tamano":
        _agregar_flag(video, "ESTIMACION_BITRATE")


def _agregar_flag(video: VideoAnaliticaDTO, flag: FlagContexto) -> None:
    if video.flags_contexto is None:
        video.flags_contexto = [flag]
        return
    if flag not in video.flags_contexto:
        video.flags_contexto.append(flag)


def agrupar_en_buckets(videos: List[VideoAnaliticaDTO]) -> Dict[str, List[VideoAnaliticaDTO]]:
    """Organizar los videos en buckets utilizando resolucion y fps."""
    buckets: Dict[str, List[VideoAnaliticaDTO]] = {}
    for video in videos:
        bucket_id = video.bucket_resolucion_fps or _resolver_bucket_resolucion(video)
        if bucket_id is None:
            bucket_id = _BUCKET_DESCONOCIDO
        video.bucket_resolucion_fps = bucket_id
        buckets.setdefault(bucket_id, []).append(video)
    return buckets


def calcular_metricas_bucket(
    bucket_id: str,
    videos: List[VideoAnaliticaDTO],
) -> BucketResumenDTO:
    """Calcular estadisticas agregadas para los videos del bucket indicado."""
    valores_mb = [video.mb_por_minuto for video in videos if video.mb_por_minuto is not None]
    promedio_mb = _promedio(valores_mb)
    desviacion_std = _desviacion_std(valores_mb)
    mediana = _mediana(valores_mb)
    mad = _mad(valores_mb, mediana)

    valores_bitrate = [video.bitrate_total_estimado for video in videos if video.bitrate_total_estimado]
    promedio_bitrate = _promedio(valores_bitrate)

    return BucketResumenDTO(
        bucket_id=bucket_id,
        promedio_mb_min=promedio_mb,
        promedio_bitrate=int(round(promedio_bitrate)) if promedio_bitrate is not None else None,
        total_videos=len(videos),
        desviacion_std_mb_min=desviacion_std,
        mediana_mb_min=mediana,
        mad_mb_min=mad,
    )


def marcar_outliers(
    videos: List[VideoAnaliticaDTO],
    bucket_resumen: BucketResumenDTO,
    umbrales: UmbralesOutliers,
) -> List[VideoAnaliticaDTO]:
    """Devolver los videos con flags de outlier segun los umbrales proporcionados."""
    if not videos:
        return videos

    umbrales_mb = umbrales.get("mb_por_minuto", {})
    umbral_suave = umbrales_mb.get("outlier_suave", 2.0)
    umbral_fuerte = umbrales_mb.get("outlier_fuerte", 3.0)
    min_bucket = umbrales.get("min_bucket", _MIN_BUCKET_CONFIABLE)

    mediana = bucket_resumen.mediana_mb_min
    mad = bucket_resumen.mad_mb_min
    denominador = _MAD_FACTOR * mad if mad and mad > 0 else None
    bucket_pequeno = bucket_resumen.total_videos < min_bucket

    for video in videos:
        if bucket_pequeno:
            _agregar_flag(video, "BUCKET_PEQUENO")

        valor = video.mb_por_minuto
        if valor is None or mediana is None or mediana <= 0:
            video.ratio_vs_promedio_bucket = None
            continue

        video.ratio_vs_promedio_bucket = valor / mediana
        if denominador is None:
            continue

        z_score = (valor - mediana) / denominador
        abs_z = abs(z_score)
        if abs_z >= umbral_fuerte:
            _agregar_flag(video, "OUTLIER_FUERTE")
            bucket_resumen.videos_outliers.append(str(video.archivo.ruta))
        elif abs_z >= umbral_suave:
            _agregar_flag(video, "OUTLIER_SUAVE")
            bucket_resumen.videos_outliers.append(str(video.archivo.ruta))

    return videos
