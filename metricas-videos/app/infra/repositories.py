"""Definiciones de repositories para filesystem y exclusiones."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from app.dominio.dtos import VideoArchivoDTO


class FilesystemRepository:
    """Acceso al filesystem para localizar archivos de video."""

    def __init__(
        self,
        extensiones_permitidas: Optional[List[str]],
        exclusiones: Optional[set[Path]] = None,
    ) -> None:
        """Definir patrones de archivos aceptados."""
        self._extensiones_permitidas = [
            self._normalizar_extension(ext) for ext in (extensiones_permitidas or [])
        ]
        self._exclusiones = {
            self._normalizar_path(exclusion) for exclusion in (exclusiones or set())
        }

    def listar_archivos_video(self, raiz: Path) -> Iterable[Path]:
        """Recorrer la carpeta raiz y devolver las rutas de video encontradas."""
        raiz_normalizada = self._normalizar_path(raiz)
        if not raiz_normalizada.exists():
            raise FileNotFoundError(f"La ruta '{raiz}' no existe")
        if not raiz_normalizada.is_dir():
            raise NotADirectoryError(f"La ruta '{raiz}' no es una carpeta valida")

        for ruta in raiz_normalizada.rglob("*"):
            if not ruta.is_file():
                continue
            if self._extensiones_permitidas and ruta.suffix.lower() not in self._extensiones_permitidas:
                continue
            if self._esta_excluida(ruta):
                continue
            yield ruta

    def construir_video_archivo(self, ruta: Path) -> VideoArchivoDTO:
        """Mapear metadatos basicos del filesystem a un DTO de video."""
        ruta_normalizada = self._normalizar_path(ruta)
        if not ruta_normalizada.exists():
            raise FileNotFoundError(f"La ruta '{ruta}' no existe")
        if not ruta_normalizada.is_file():
            raise FileNotFoundError(f"La ruta '{ruta}' no es un archivo valido")

        stat = ruta_normalizada.stat()
        return VideoArchivoDTO(
            ruta=ruta_normalizada,
            size_bytes=stat.st_size,
            fecha_modificacion=datetime.fromtimestamp(stat.st_mtime),
        )

    @staticmethod
    def _normalizar_extension(valor: str) -> str:
        valor = valor.strip().lower()
        if not valor:
            raise ValueError("Las extensiones permitidas no pueden estar vacias")
        if not valor.startswith("."):
            valor = f".{valor}"
        return valor

    @staticmethod
    def _normalizar_path(ruta: Path) -> Path:
        return ruta.expanduser().resolve()

    def _esta_excluida(self, ruta: Path) -> bool:
        ruta_normalizada = self._normalizar_path(ruta)
        for exclusion in self._exclusiones:
            if ruta_normalizada == exclusion or ruta_normalizada.is_relative_to(exclusion):
                return True
        return False
