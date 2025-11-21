"""Declaraciones de configuraciones principales del pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional
import logging


@dataclass
class Settings:
    """Representa los parámetros configurables para ejecutar el workflow.

    Attributes
    ----------
    raiz_media:
        Carpeta raíz en donde se buscarán los videos a procesar.
    ruta_exclusiones:
        Lista opcional de rutas puntuales que deben ignorarse aun cuando
        se encuentren dentro de ``raiz_media``.
    patrones_video:
        Extensiones de archivos que se considerarán videos válidos para el
        análisis. Debe existir el encabezado correspondiente en el archivo de
        configuración.
    output_excel:
        Ruta del archivo donde se generará el reporte consolidado.
    ffmpeg_bin / ffprobe_bin:
        Rutas a los ejecutables necesarios para extraer metadatos de video.
    """

    raiz_media: Path
    ruta_exclusiones: Optional[List[Path]]
    patrones_video: List[str]
    output_excel: Path

    @staticmethod
    def _to_path(value: str, nombre_campo: str) -> Path:
        return Path(value).expanduser()

    @classmethod
    def _cargar_lista_paths(
        cls, valores: Optional[Iterable[str]], nombre_campo: str
    ) -> Optional[List[Path]]:
        if valores is None:
            return None
        if isinstance(valores, (str, Path)):
            return [cls._to_path(str(valores), nombre_campo)]
        try:
            return [cls._to_path(str(valor), nombre_campo) for valor in valores]
        except TypeError as exc:  # pragma: no cover - defensivo
            raise ValueError(
                f"El campo '{nombre_campo}' debe ser una lista de rutas"
            ) from exc

    @staticmethod
    def _normalizar_extension(valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("Las extensiones de video no pueden estar vacías")
        if not valor.startswith("."):
            valor = f".{valor}"
        return valor.lower()

    @staticmethod
    def _limpiar_linea_config(valor: str) -> str:
        valor = valor.strip()
        if valor.startswith(('"', "'")) and valor.endswith(('"', "'")):
            valor = valor[1:-1]
        return valor.strip()

    @classmethod
    def _parsear_config_txt(cls, contenido: str) -> dict[str, list[str]]:
        secciones: dict[str, list[str]] = {}
        titulo_actual: Optional[str] = None
        buffer: list[str] = []

        for linea in contenido.splitlines():
            linea_stripped = linea.strip()
            if not linea_stripped:
                if titulo_actual is not None and buffer:
                    buffer.append("")
                continue
            if linea_stripped.startswith("#"):
                if titulo_actual is not None:
                    secciones[titulo_actual] = [valor for valor in buffer if valor.strip()]
                titulo_actual = linea_stripped[1:].strip().lower()
                buffer = []
            else:
                buffer.append(linea)

        if titulo_actual is not None:
            secciones[titulo_actual] = [valor for valor in buffer if valor.strip()]

        return secciones

    @classmethod
    def cargar_desde_txt(cls, ruta: Path) -> "Settings":
        """Construir la configuración leyendo un archivo de texto estructurado."""

        contenido = ruta.read_text(encoding="utf-8")
        secciones = cls._parsear_config_txt(contenido)

        def obtener_una_linea(nombre: str) -> str:
            try:
                valores = secciones[nombre]
            except KeyError as exc:
                raise ValueError(
                    f"Falta el encabezado '# {nombre}' en el archivo de configuración"
                ) from exc
            if not valores:
                raise ValueError(
                    f"El encabezado '# {nombre}' no contiene ninguna línea con datos"
                )
            if len(valores) > 1:
                raise ValueError(
                    f"El encabezado '# {nombre}' solo admite una línea, se recibieron {len(valores)}"
                )
            
            valor = cls._limpiar_linea_config(valores[0])
            if valor == "null":
                return ""
            return valor

        raiz_media = cls._to_path(obtener_una_linea("raiz_media"), "raiz_media")
        ruta_debug = obtener_una_linea("ruta_debug")
        if ruta_debug != "":
            ruta_debug = cls._to_path(ruta_debug, "ruta_debug")
            logging.warning("Se está utilizando ruta debug")
            raiz_media = ruta_debug
        output_excel = cls._to_path(obtener_una_linea("output_excel"), "output_excel")

        try:
            patrones_brutos = secciones["patrones_video"]
        except KeyError as exc:
            raise ValueError(
                "Falta el encabezado '# patrones_video' en el archivo de configuración"
            ) from exc
        patrones_video: list[str] = []
        for linea in patrones_brutos:
            for candidato in linea.split(","):
                candidato_limpio = cls._limpiar_linea_config(candidato)
                if candidato_limpio:
                    patrones_video.append(cls._normalizar_extension(candidato_limpio))

        if not patrones_video:
            raise ValueError(
                "El encabezado '# patrones_video' no contiene ninguna extensión válida"
            )

        ruta_exclusiones_brutas = secciones.get("ruta_exclusiones")
        ruta_exclusiones = cls._cargar_lista_paths(
            [cls._limpiar_linea_config(linea) for linea in ruta_exclusiones_brutas]
            if ruta_exclusiones_brutas
            else None,
            "ruta_exclusiones",
        )

        return cls(
            raiz_media=raiz_media,
            ruta_exclusiones=ruta_exclusiones,
            patrones_video=patrones_video,
            output_excel=output_excel,
        )

    def cargar(self) -> "Settings":
        """Devolver la instancia lista para el pipeline (placeholder para validaciones)."""

        return self

    @classmethod
    def ruta_config_por_defecto(cls) -> Path:
        """Ruta del archivo settings.txt que acompaña a este módulo."""

        return Path(__file__).resolve().with_name("settings.txt")

    @classmethod
    def cargar_por_defecto(cls) -> "Settings":
        """Cargar configuración desde el settings.txt ubicado junto a este archivo."""

        return cls.cargar_desde_txt(cls.ruta_config_por_defecto())
