from dataclasses import dataclass
import json
import os
import subprocess
import logging
import uuid

def procesar_archivos(rutas: list[str]):
    for ruta in rutas:
        info = obtener_info_video(ruta)
        if info.fps is None:
            logging.error(f"No se pudo obtener FPS de: {ruta}")
            continue
        logging.info(f"Información extraída para '{ruta}': {info}")
        
        # comando = generar_comando_ffmpeg(ruta, info)
        comando = None
        if comando:
            ejecutar_ffmpeg(comando)
        else:
            logging.warning(f"Comando no generado para: {ruta}")

@dataclass
class VideoInfo:
    fps: float | None = None
    audio_bitrate: int | None = None
    video_bitrate: int | None = None
    width: int | None = None
    height: int | None = None

def obtener_info_video(ruta: str) -> VideoInfo:
    info = VideoInfo()

    try:
        resultado = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=bit_rate", 
                "-show_entries", "stream=index,codec_type,r_frame_rate,bit_rate,width,height",
                "-of", "json",
                ruta
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        data = json.loads(resultado.stdout)
        
        # Bitrate promedio total del archivo
        info.video_bitrate = int(data["format"]["bit_rate"])

        streams = data["streams"]
        video_stream = next(s for s in streams if s["codec_type"] == "video")
        audio_stream = next(s for s in streams if s["codec_type"] == "audio")

        # FPS
        r_frame_rate = video_stream["r_frame_rate"]
        num, denom = map(int, r_frame_rate.split("/"))
        info.fps = num / denom if denom != 0 else None

        # Resolución
        info.width = video_stream["width"]
        info.height = video_stream["height"]

        # Bitrate de audio
        info.audio_bitrate = int(audio_stream["bit_rate"]) if "bit_rate" in audio_stream else 0


    except Exception as e:
        logging.error(f"Error al obtener información del video '{ruta}': {e}")

    return info

def generar_comando_ffmpeg(path: str, info: VideoInfo) -> list[str] | None:
    """
    Genera el comando ffmpeg para convertir el video a 480p usando el encoder h264_nvenc.

    - Si los FPS del video original son mayores a 40, se fuerza la reducción a 30 FPS.
    - Si son 40 o menos, se mantiene la tasa original y no se aplica el filtro fps.
    - El audio se recodifica a AAC 160 kbps solo si su bitrate original es mayor a 192 kbps.
    - Si el archivo de salida ya existe, se agrega un sufijo único con un GUID para evitar sobrescritura.

    El archivo de salida queda en la misma carpeta que el original, con sufijo '_converted[_guid].ext'.

    Parámetros:
        path (str): Ruta absoluta al archivo de video original.
        info (VideoInfo): Contiene FPS y bitrate de audio detectados.

    Retorna:
        list[str] | None: Lista de argumentos para ffmpeg o None si ocurre algún error.
    """
    try:
        carpeta, nombre = os.path.split(path)
        nombre_base, extension = os.path.splitext(nombre)
        nombre_salida = f"{nombre_base}_converted{extension}"
        path_salida = os.path.join(carpeta, nombre_salida)

        # Si el archivo de salida ya existe, agregar GUID
        if os.path.exists(path_salida):
            guid = uuid.uuid4().hex[:8]
            nombre_salida = f"{nombre_base}_converted_{guid}{extension}"
            path_salida = os.path.join(carpeta, nombre_salida)
            logging.warning(f"Archivo de salida ya existe. Usando nombre alternativo: {nombre_salida}")

        # Armado del filtro de video
        filtros = ["hwupload_cuda", "scale_cuda=w=-2:h=480"]
        if info.fps and info.fps > 40:
            filtros.append("fps=30")
        filtro_vf = ",".join(filtros)

        if info.audio_bitrate > 192000:
            logging.info(f"Bitrate de audio alto ({info.audio_bitrate}); se recodificará a 160k.")
            audio_args = ["-c:a", "aac", "-b:a", "160k"]
        else:
            logging.info(f"Bitrate de audio aceptable ({info.audio_bitrate}); se conservará el original.")
            audio_args = ["-c:a", "copy"]


        return [
            "ffmpeg",
            "-i", path,
            "-vf", filtro_vf,
            "-c:v", "h264_nvenc",
            "-preset", "p3",
            "-cq", "23",
            *audio_args,
            path_salida
        ]

    except Exception as e:
        logging.error(f"Error al generar comando ffmpeg para '{path}': {e}")
        return None

def ejecutar_ffmpeg(comando: list[str]):
    try:
        logging.info(f"Ejecutando FFmpeg: {' '.join(comando)}")
        
        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if resultado.returncode == 0:
            logging.info("Conversión completada con éxito.")
        else:
            logging.error(f"Error en la conversión. Código: {resultado.returncode}")
            logging.error(resultado.stderr.strip())
    
    except Exception as e:
        logging.error(f"Error al ejecutar FFmpeg: {e}")