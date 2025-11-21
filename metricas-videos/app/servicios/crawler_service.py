"""Servicio encargado de explorar carpetas y aplicar exclusiones."""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.dominio.dtos import VideoArchivoDTO
from app.infra.repositories import FilesystemRepository


def buscar_videos_en_arbol(
    raiz: Path,
    repository: FilesystemRepository,
) -> List[VideoArchivoDTO]:
    """Recorrer la estructura de carpetas y devolver archivos elegibles como DTOs."""
    rutas = repository.listar_archivos_video(raiz)
    videos = [repository.construir_video_archivo(ruta) for ruta in rutas]
    return sorted(videos, key=lambda video: video.ruta.as_posix())
