# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingTypeArgument=false, reportCallIssue=false, reportUnknownArgumentType=false
"""Servicio responsable de exportar la informacion recopilada a Excel."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping, Sequence, Optional, TYPE_CHECKING, Any, cast

import xlsxwriter

from app.dominio.dtos import BucketResumenDTO, VideoAnaliticaDTO
from app.servicios.excel_toolings import agregar_funcionalidades_al_archivo


VideoExtractor = Callable[[VideoAnaliticaDTO], object | None]
BucketExtractor = Callable[[BucketResumenDTO], object | None]

if TYPE_CHECKING:
    from xlsxwriter.workbook import Workbook as WorkbookType
    from xlsxwriter.worksheet import Worksheet as WorksheetType
    from xlsxwriter.chart import Chart as ChartType
    from xlsxwriter.format import Format as FormatType
else:
    WorkbookType = Any  # type: ignore[misc]
    WorksheetType = Any  # type: ignore[misc]
    ChartType = Any  # type: ignore[misc]
    FormatType = Any  # type: ignore[misc]

_SHEET_VIDEOS = "Videos Detalle"
_SHEET_BUCKETS = "Buckets Resumen"
_SHEET_OUTLIERS = "Outliers"
_SHEET_DASHBOARD = "Dashboard"


def _col_archivo_ruta(video: VideoAnaliticaDTO) -> str:
    return str(video.archivo.ruta)


def _col_archivo_size(video: VideoAnaliticaDTO) -> int:
    return video.archivo.size_bytes


def _col_duracion(video: VideoAnaliticaDTO) -> float:
    return video.stream_video.duracion_seg


def _col_mb_por_minuto(video: VideoAnaliticaDTO) -> Optional[float]:
    return video.mb_por_minuto


def _col_bitrate_total(video: VideoAnaliticaDTO) -> Optional[int]:
    return video.bitrate_total_estimado


def _col_kbps_total(video: VideoAnaliticaDTO) -> Optional[int]:
    return video.kbps_total


def _col_kbps_video(video: VideoAnaliticaDTO) -> Optional[int]:
    return video.kbps_video


def _col_bppf(video: VideoAnaliticaDTO) -> Optional[float]:
    return video.bits_por_pixel_frame


def _col_audio_share(video: VideoAnaliticaDTO) -> Optional[float]:
    return video.audio_share_pct


def _col_duracion_categoria(video: VideoAnaliticaDTO) -> Optional[str]:
    return video.duracion_categoria


def _col_bucket(video: VideoAnaliticaDTO) -> Optional[str]:
    return video.bucket_resolucion_fps


def _col_ratio_bucket(video: VideoAnaliticaDTO) -> Optional[float]:
    return video.ratio_vs_promedio_bucket


def _col_fps(video: VideoAnaliticaDTO) -> float:
    return video.stream_video.fps


def _col_flags(video: VideoAnaliticaDTO) -> str:
    return ", ".join(video.flags_contexto or [])


_VIDEO_HEADERS: list[tuple[str, VideoExtractor]] = [
    ("archivo.ruta (origen del archivo)", _col_archivo_ruta),
    ("archivo.size_bytes (bytes totales)", _col_archivo_size),
    ("stream_video.duracion_seg (duración en s)", _col_duracion),
    ("mb_por_minuto (MB/min útil para peso relativo)", _col_mb_por_minuto),
    ("bitrate_total_estimado (bps estimado total)", _col_bitrate_total),
    ("kbps_total (lectura rápida kbps)", _col_kbps_total),
    ("kbps_video (bitrate de video)", _col_kbps_video),
    ("bits_por_pixel_frame (eficiencia compresión)", _col_bppf),
    ("audio_share_pct (% peso audio)", _col_audio_share),
    ("duracion_categoria (contexto duración)", _col_duracion_categoria),
    ("bucket_resolucion_fps (clave de bucket)", _col_bucket),
    ("ratio_vs_promedio_bucket (comparación bucket)", _col_ratio_bucket),
    ("fps (frames por segundo)", _col_fps),
    ("flags_contexto (diagnóstico)", _col_flags),
]


def _col_bucket_id(bucket: BucketResumenDTO) -> str:
    return bucket.bucket_id


def _col_total_videos(bucket: BucketResumenDTO) -> int:
    return bucket.total_videos


def _col_promedio_mb(bucket: BucketResumenDTO) -> Optional[float]:
    return bucket.promedio_mb_min


def _col_mediana_mb(bucket: BucketResumenDTO) -> Optional[float]:
    return bucket.mediana_mb_min


def _col_mad_mb(bucket: BucketResumenDTO) -> Optional[float]:
    return bucket.mad_mb_min


def _col_std_mb(bucket: BucketResumenDTO) -> Optional[float]:
    return bucket.desviacion_std_mb_min


def _col_promedio_bitrate(bucket: BucketResumenDTO) -> Optional[int]:
    return bucket.promedio_bitrate


def _col_videos_outliers(bucket: BucketResumenDTO) -> str:
    return ", ".join(bucket.videos_outliers)


_BUCKET_HEADERS: list[tuple[str, BucketExtractor]] = [
    ("bucket_id (clave resolucion@fps)", _col_bucket_id),
    ("total_videos (cantidad en bucket)", _col_total_videos),
    ("promedio_mb_min (MB/min promedio)", _col_promedio_mb),
    ("mediana_mb_min (mediana robusta)", _col_mediana_mb),
    ("mad_mb_min (MAD para z robusto)", _col_mad_mb),
    ("desviacion_std_mb_min (std clásica)", _col_std_mb),
    ("promedio_bitrate (bitrate promedio)", _col_promedio_bitrate),
    ("videos_outliers (rutas marcadas)", _col_videos_outliers),
]

_OUTLIER_FLAGS = {"OUTLIER_FUERTE", "OUTLIER_SUAVE", "BUCKET_PEQUENO"}


def generar_excel_resumen(
    output_path: Path,
    videos: Sequence[VideoAnaliticaDTO],
    bucket_resumenes: Mapping[str, BucketResumenDTO],
) -> None:
    """Crear el archivo Excel con detalle por video y resumen de buckets."""
    if not videos:
        raise ValueError("Se requieren videos para generar el Excel.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook: WorkbookType = xlsxwriter.Workbook(output_path.as_posix())  # type: ignore[call-arg]

    formatos = _crear_formatos(workbook)
    _render_videos_detalle(workbook, formats=formatos, videos=videos)
    _render_buckets_resumen(workbook, formats=formatos, bucket_resumenes=bucket_resumenes)
    outlier_videos = [video for video in videos if _es_outlier(video)]
    _render_outliers(workbook, formats=formatos, outliers=outlier_videos)
    _render_dashboard(workbook, videos=videos, bucket_resumenes=bucket_resumenes)
    agregar_funcionalidades_al_archivo(
        workbook=workbook,
        formats=formatos,
        output_path=output_path,
        outlier_paths=[str(video.archivo.ruta) for video in outlier_videos],
    )

    workbook.close()


def _crear_formatos(workbook: WorkbookType) -> dict[str, FormatType]:
    return {
        "header": workbook.add_format({"bold": True, "bg_color": "#F0F0F0"}),
        "entero": workbook.add_format({"num_format": "#,##0"}),
        "decimal": workbook.add_format({"num_format": "0.00"}),
        "ratio": workbook.add_format({"num_format": "0.00"}),
        "porcentaje": workbook.add_format({"num_format": '0.00"%"'}),
        "texto": workbook.add_format({"text_wrap": False}),
        "bucket_warning": workbook.add_format({"bg_color": "#FFF2CC"}),
    }


def _render_videos_detalle(
    workbook: WorkbookType,
    *,
    formats: dict[str, FormatType],
    videos: Sequence[VideoAnaliticaDTO],
) -> None:
    hoja: WorksheetType = workbook.add_worksheet(_SHEET_VIDEOS)
    hoja.freeze_panes(1, 0)

    headers = [titulo for titulo, _ in _VIDEO_HEADERS]
    hoja.write_row(0, 0, headers, formats["header"])

    rows: list[list[object | None]] = []
    for video in videos:
        fila: list[object | None] = []
        for _, getter in _VIDEO_HEADERS:
            fila.append(getter(video))
        rows.append(fila)

    for idx, fila in enumerate(rows, start=1):
        for col, valor in enumerate(fila):
            hoja.write(idx, col, valor, _resolver_formato_videos(col, formats))

    hoja.add_table(
        0,
        0,
        len(rows),
        len(headers) - 1,
        {
            "name": "VideosDetalle",
            "columns": [{"header": header} for header in headers],
        },
    )

    hoja.set_column(0, 0, 45)
    hoja.set_column(1, 1, 14, formats["entero"])
    hoja.set_column(2, 2, 16, formats["decimal"])
    hoja.set_column(3, 7, 18, formats["decimal"])
    hoja.set_column(8, 8, 16, formats["porcentaje"])
    hoja.set_column(9, 10, 20, formats["texto"])
    hoja.set_column(11, 12, 20, formats["decimal"])
    hoja.set_column(13, 13, 28, formats["texto"])


def _resolver_formato_videos(col: int, formats: dict[str, FormatType]) -> FormatType | None:
    if col in {1, 4, 5, 6}:
        return formats["entero"]
    if col in {2, 3, 7, 12}:
        return formats["decimal"]
    if col == 11:
        return formats["ratio"]
    if col == 8:
        return formats["porcentaje"]
    return None


def _render_buckets_resumen(
    workbook: WorkbookType,
    *,
    formats: dict[str, FormatType],
    bucket_resumenes: Mapping[str, BucketResumenDTO],
) -> None:
    hoja: WorksheetType = workbook.add_worksheet(_SHEET_BUCKETS)
    hoja.freeze_panes(1, 0)

    headers = [titulo for titulo, _ in _BUCKET_HEADERS]
    hoja.write_row(0, 0, headers, formats["header"])

    buckets = [bucket_resumenes[key] for key in sorted(bucket_resumenes.keys())]

    for fila_idx, bucket in enumerate(buckets, start=1):
        for col_idx, (_, getter) in enumerate(_BUCKET_HEADERS):
            hoja.write(fila_idx, col_idx, getter(bucket), _resolver_formato_buckets(col_idx, formats))

    hoja.add_table(
        0,
        0,
        len(buckets),
        len(headers) - 1,
        {
            "name": "BucketsResumen",
            "columns": [{"header": header} for header in headers],
        },
    )

    hoja.set_column(0, 0, 28)
    hoja.set_column(1, 1, 14, formats["entero"])
    hoja.set_column(2, 6, 20, formats["decimal"])
    hoja.set_column(7, 7, 40, formats["texto"])

    for fila_idx, bucket in enumerate(buckets, start=1):
        if bucket.total_videos < 5:
            hoja.set_row(fila_idx, None, formats["bucket_warning"])


def _resolver_formato_buckets(col: int, formats: dict[str, FormatType]) -> FormatType | None:
    if col in {1, 6}:
        return formats["entero"]
    if col in {2, 3, 4, 5}:
        return formats["decimal"]
    return None


def _render_outliers(
    workbook: WorkbookType,
    *,
    formats: dict[str, FormatType],
    outliers: Sequence[VideoAnaliticaDTO],
) -> None:
    hoja: WorksheetType = workbook.add_worksheet(_SHEET_OUTLIERS)
    hoja.freeze_panes(1, 0)

    headers = [titulo for titulo, _ in _VIDEO_HEADERS]
    hoja.write_row(0, 0, headers, formats["header"])
    datos_finales = _escribir_outliers(hoja, outliers, formats)
    _agregar_totales_outliers(hoja, formats, datos_finales)


def _escribir_outliers(
    hoja: WorksheetType,
    outliers: Sequence[VideoAnaliticaDTO],
    formats: dict[str, FormatType],
) -> int:
    last_row = 0
    for fila_idx, video in enumerate(outliers, start=1):
        for col_idx, (_, getter) in enumerate(_VIDEO_HEADERS):
            hoja.write(fila_idx, col_idx, getter(video), _resolver_formato_videos(col_idx, formats))
            last_row = fila_idx
    return last_row


def _agregar_totales_outliers(
    hoja: WorksheetType,
    formats: dict[str, FormatType],
    last_row: int,
) -> None:
    if last_row == 0:
        hoja.set_column(0, len(_VIDEO_HEADERS) - 1, 24)
        return

    tabla_rows = last_row
    headers = [titulo for titulo, _ in _VIDEO_HEADERS]
    hoja.add_table(
        0,
        0,
        last_row,
        len(headers) - 1,
        {
            "name": "VideosOutliers",
            "columns": [{"header": header} for header in headers],
        },
    )

    hoja.set_column(0, len(headers) - 1, 24)

    fila_offset = last_row + 2
    hoja.write(fila_offset, 0, "")
    fila_offset += 1

    hoja.write(fila_offset, 0, "SUMA MB", formats["header"])
    rango_bytes = f"B2:B{tabla_rows + 1}"
    hoja.write_formula(
        fila_offset,
        1,
        f"=SUM({rango_bytes})/1024/1024",
        formats["decimal"],
    )
    fila_offset += 1

    hoja.write(fila_offset, 0, "SUMA GB", formats["header"])
    hoja.write_formula(
        fila_offset,
        1,
        f"=SUM({rango_bytes})/1024/1024/1024",
        formats["decimal"],
    )


def _render_dashboard(
    workbook: WorkbookType,
    *,
    videos: Sequence[VideoAnaliticaDTO],
    bucket_resumenes: Mapping[str, BucketResumenDTO],
) -> None:
    hoja: WorksheetType = workbook.add_worksheet(_SHEET_DASHBOARD)

    bucket_count = len(bucket_resumenes)
    detail_count = len(videos)

    if bucket_count:
        chart_col = cast(ChartType, workbook.add_chart({"type": "column"}))
        chart_col.add_series(
            {
                "name": "Mediana MB/min por bucket",
                "categories": [_SHEET_BUCKETS, 1, 0, bucket_count, 0],
                "values": [_SHEET_BUCKETS, 1, 3, bucket_count, 3],
            }
        )
        chart_col.set_title({"name": "Mediana MB/min por bucket"})
        chart_col.set_x_axis({"name": "Bucket"})
        chart_col.set_y_axis({"name": "MB/min"})
        hoja.insert_chart(1, 1, chart_col, {"x_scale": 1.4, "y_scale": 1.4})  # type: ignore[arg-type]

    if detail_count:
        chart_scatter = cast(ChartType, workbook.add_chart({"type": "scatter", "subtype": "straight_with_markers"}))
        chart_scatter.add_series(
            {
                "name": "MB/min vs duración",
                "categories": [_SHEET_VIDEOS, 1, 2, detail_count, 2],
                "values": [_SHEET_VIDEOS, 1, 3, detail_count, 3],
            }
        )
        chart_scatter.set_title({"name": "Dispersión MB/min vs duración"})
        chart_scatter.set_x_axis({"name": "Duración (s)"})
        chart_scatter.set_y_axis({"name": "MB/min"})
        hoja.insert_chart(18, 1, chart_scatter, {"x_scale": 1.4, "y_scale": 1.4})  # type: ignore[arg-type]

    _agregar_grafico_flags(workbook, hoja=hoja, videos=videos)
    _agregar_grafico_audio(workbook, hoja=hoja, videos=videos)


def _agregar_grafico_flags(
    workbook: WorkbookType,
    *,
    hoja: WorksheetType,
    videos: Sequence[VideoAnaliticaDTO],
) -> None:
    conteos: dict[str, int] = dict.fromkeys(_OUTLIER_FLAGS, 0)
    for video in videos:
        for flag in video.flags_contexto or []:
            if flag in conteos:
                conteos[flag] += 1

    if sum(conteos.values()) == 0:
        return

    inicio_fila = 1
    inicio_col = 9
    hoja.write(inicio_fila, inicio_col, "Flag", workbook.add_format({"bold": True}))
    hoja.write(inicio_fila, inicio_col + 1, "Cantidad", workbook.add_format({"bold": True}))

    for idx, (flag, count) in enumerate(conteos.items(), start=1):
        hoja.write(inicio_fila + idx, inicio_col, flag)
        hoja.write(inicio_fila + idx, inicio_col + 1, count)

    chart = cast(ChartType, workbook.add_chart({"type": "column"}))
    chart.add_series(
        {
            "name": "Flags de outlier",
            "categories": ["Dashboard", inicio_fila + 1, inicio_col, inicio_fila + len(conteos), inicio_col],
            "values": ["Dashboard", inicio_fila + 1, inicio_col + 1, inicio_fila + len(conteos), inicio_col + 1],
        }
    )
    chart.set_title({"name": "Distribución de flags"})
    chart.set_x_axis({"name": "Flag"})
    chart.set_y_axis({"name": "Cantidad"})
    hoja.insert_chart(inicio_fila + 5, inicio_col, chart, {"x_scale": 1.1, "y_scale": 1.1})  # type: ignore[arg-type]


def _agregar_grafico_audio(
    workbook: WorkbookType,
    *,
    hoja: WorksheetType,
    videos: Sequence[VideoAnaliticaDTO],
) -> None:
    top_videos = sorted(
        [video for video in videos if video.audio_share_pct is not None],
        key=lambda v: v.audio_share_pct or 0,
        reverse=True,
    )[:10]

    if not top_videos:
        return

    inicio_fila = 20
    inicio_col = 9

    hoja.write(inicio_fila, inicio_col, "Video", workbook.add_format({"bold": True}))
    hoja.write(inicio_fila, inicio_col + 1, "Audio %", workbook.add_format({"bold": True}))
    hoja.write(inicio_fila, inicio_col + 2, "Video %", workbook.add_format({"bold": True}))

    for idx, video in enumerate(top_videos, start=1):
        audio_pct = video.audio_share_pct or 0
        hoja.write(inicio_fila + idx, inicio_col, video.archivo.ruta.name)
        hoja.write(inicio_fila + idx, inicio_col + 1, audio_pct)
        hoja.write(inicio_fila + idx, inicio_col + 2, max(0, 100 - audio_pct))

    chart = cast(ChartType, workbook.add_chart({"type": "column", "subtype": "stacked"}))
    chart.add_series(
        {
            "name": "Audio",
            "categories": ["Dashboard", inicio_fila + 1, inicio_col, inicio_fila + len(top_videos), inicio_col],
            "values": ["Dashboard", inicio_fila + 1, inicio_col + 1, inicio_fila + len(top_videos), inicio_col + 1],
        }
    )
    chart.add_series(
        {
            "name": "Video",
            "categories": ["Dashboard", inicio_fila + 1, inicio_col, inicio_fila + len(top_videos), inicio_col],
            "values": ["Dashboard", inicio_fila + 1, inicio_col + 2, inicio_fila + len(top_videos), inicio_col + 2],
        }
    )
    chart.set_title({"name": "Peso relativo de audio vs video (Top 10)"})
    chart.set_x_axis({"name": "Video"})
    chart.set_y_axis({"name": "Porcentaje"})
    hoja.insert_chart(inicio_fila + 2, inicio_col + 4, chart, {"x_scale": 1.2, "y_scale": 1.2})  # type: ignore[arg-type]


def _es_outlier(video: VideoAnaliticaDTO) -> bool:
    return any(flag in _OUTLIER_FLAGS for flag in (video.flags_contexto or []))
