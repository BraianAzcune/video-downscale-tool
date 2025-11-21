# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingTypeArgument=false, reportCallIssue=false, reportUnknownArgumentType=false

"""Gateway que encapsula interacciones con ffprobe usando ffmpeg-python."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import ffmpeg

from app.dominio.dtos import AudioStreamDTO, VideoStreamDTO


class FFMPEFGateway:
    """Interfaz de alto nivel para extraer metadata tecnica mediante ffprobe."""

    def obtener_streams(self, ruta: Path) -> Tuple[VideoStreamDTO, List[AudioStreamDTO]]:
        """Ejecutar ffprobe y devolver los DTOs de video y audio."""
        data_ffprobe = self._ejecutar_ffprobe_json(ruta)
        stream_video = self._mapear_stream_video(data_ffprobe)
        streams_audio = self._mapear_streams_audio(data_ffprobe)
        return stream_video, streams_audio

    def _ejecutar_ffprobe_json(self, ruta: Path) -> Dict:
        """Invocar ffprobe (via ffmpeg-python) y devolver la respuesta como dict."""
        ruta_normalizada = ruta.expanduser().resolve()
        if not ruta_normalizada.exists():
            raise FileNotFoundError(f"La ruta '{ruta}' no existe")
        if not ruta_normalizada.is_file():
            raise FileNotFoundError(f"La ruta '{ruta}' no es un archivo valido")

        try:
            return ffmpeg.probe(str(ruta_normalizada))
        except ffmpeg.Error as exc:  # pragma: no cover - depende del entorno ffmpeg
            stderr = exc.stderr.decode("utf-8", errors="ignore") if isinstance(exc.stderr, bytes) else exc.stderr
            raise RuntimeError(f"ffprobe fallo al analizar '{ruta_normalizada}': {stderr}") from exc

    def _mapear_stream_video(self, data_ffprobe: Dict) -> VideoStreamDTO:
        """Convertir el primer stream de video en un DTO."""
        stream_video = self._obtener_stream_por_tipo(data_ffprobe.get("streams", []), "video")
        if stream_video is None:
            raise ValueError("ffprobe no devolvio streams de video")

        avg_frame_rate = stream_video.get("avg_frame_rate", "0/0")
        ref_frame_rate = stream_video.get("r_frame_rate", "0/0")
        format_info = data_ffprobe.get("format", {})
        duracion_seg = self._parse_float(stream_video.get("duration")) or self._parse_float(
            format_info.get("duration")
        )
        contenedor = format_info.get("format_name") or stream_video.get("codec_tag_string") or "desconocido"
        bitrate_container_bps = self._parse_int(format_info.get("bit_rate"))

        return VideoStreamDTO(
            duracion_seg=duracion_seg,
            contenedor=contenedor,
            codec=stream_video.get("codec_name", "desconocido"),
            bitrate_bps=self._parse_int(stream_video.get("bit_rate")),
            bitrate_container_bps=bitrate_container_bps,
            width=int(stream_video.get("width") or 0),
            height=int(stream_video.get("height") or 0),
            fps=self._parse_frame_rate(avg_frame_rate),
            pix_fmt=stream_video.get("pix_fmt", "desconocido"),
            profile=stream_video.get("profile"),
            level=self._parse_str(stream_video.get("level")),
            color_space=stream_video.get("color_space"),
            color_transfer=stream_video.get("color_transfer"),
            color_primaries=stream_video.get("color_primaries"),
            es_hdr=self._es_hdr(stream_video),
            es_vfr=self._parse_frame_rate(avg_frame_rate) != self._parse_frame_rate(ref_frame_rate),
        )

    def _mapear_streams_audio(self, data_ffprobe: Dict) -> List[AudioStreamDTO]:
        """Mapear todos los streams de audio presentes en la respuesta."""
        streams_audio = [
            stream for stream in data_ffprobe.get("streams", []) if stream.get("codec_type") == "audio"
        ]
        if not streams_audio:
            return []

        dto_list: List[AudioStreamDTO] = []
        for stream in streams_audio:
            dto_list.append(
                AudioStreamDTO(
                    codec=stream.get("codec_name", "desconocido"),
                    bitrate_bps=self._parse_int(stream.get("bit_rate")),
                    channels=int(stream.get("channels") or 0),
                    sample_rate=int(stream.get("sample_rate") or 0),
                    layout=stream.get("channel_layout"),
                )
            )
        return dto_list

    @staticmethod
    def _obtener_stream_por_tipo(streams: Iterable[Dict], tipo: str) -> Optional[Dict]:
        for stream in streams:
            if stream.get("codec_type") == tipo:
                return stream
        return None

    @staticmethod
    def _parse_int(valor: Optional[str]) -> Optional[int]:
        if valor is None or valor == "N/A":
            return None
        try:
            return int(float(valor))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_frame_rate(valor: str) -> float:
        if not valor or valor in {"0/0", "N/A"}:
            return 0.0
        if "/" not in valor:
            try:
                return float(valor)
            except ValueError:
                return 0.0
        numerador, denominador = valor.split("/", 1)
        try:
            num = float(numerador)
            den = float(denominador)
            if den == 0:
                return 0.0
            return num / den
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_float(valor: Optional[str]) -> float:
        if valor in (None, "N/A"):
            return 0.0
        try:
            return float(valor)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_str(valor: Optional[str]) -> Optional[str]:
        if valor is None:
            return None
        valor = str(valor).strip()
        return valor or None

    @staticmethod
    def _es_hdr(stream_video: Dict) -> bool:
        transfer = (stream_video.get("color_transfer") or "").lower()
        primaries = (stream_video.get("color_primaries") or "").lower()
        hdr_transfers = {"smpte2084", "arib-std-b67"}
        return transfer in hdr_transfers or primaries == "bt2020"
