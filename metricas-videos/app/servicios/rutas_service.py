"""Servicios utilitarios para construir rutas de salida basadas en la fuente analizada."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def resolver_destino_con_timestamp(
    base_salida: Path,
    origen: Path,
    *,
    sufijo_por_defecto: str = ".xlsx",
) -> Path:
    """Crear una carpeta y archivo con timestamp y nombre derivado del origen."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    origen_sanitizado = sanitizar_path(origen)
    nombre_base = f"{origen_sanitizado}_{timestamp}"
    carpeta = base_salida.parent / nombre_base
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre_archivo = f"{nombre_base}{base_salida.suffix or sufijo_por_defecto}"
    return carpeta / nombre_archivo


def sanitizar_path(path: Path) -> str:
    """Reemplazar caracteres conflictivos (:, \\, /) por guiones."""
    texto = str(path)
    for caracter in (":", "\\", "/"):
        texto = texto.replace(caracter, "-")
    texto = texto.strip("-")
    return texto or "metricas"
