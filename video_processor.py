from dataclasses import dataclass
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
        logging.info(f"FPS obtenidos para '{ruta}': {info.fps:.2f}")
        
        comando = generar_comando_ffmpeg(ruta, info)
        if comando:
            ejecutar_ffmpeg(comando)
        else:
            logging.warning(f"Comando no generado para: {ruta}")

@dataclass
class VideoInfo:
    fps: float | None
    audio_bitrate: int | None

def obtener_info_video(ruta: str) -> VideoInfo:
    """
    Retorna los FPS y el bitrate de audio del archivo especificado.
    Busca el primer stream de tipo 'video' y 'audio' respectivamente.
    """
    fps = None
    audio_bitrate = None
    tipo_actual = None

    try:
        resultado = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "stream=index,codec_type,r_frame_rate,bit_rate",
                "-of", "default=noprint_wrappers=1",
                ruta
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        for linea in resultado.stdout.splitlines():
            if linea.startswith("codec_type="):
                tipo_actual = linea.split("=")[1].strip()

            elif tipo_actual == "video" and fps is None and linea.startswith("r_frame_rate="):
                valor = linea.split("=")[1]
                if "/" in valor:
                    num, denom = map(int, valor.split("/"))
                    fps = num / denom if denom != 0 else None

            elif tipo_actual == "audio" and audio_bitrate is None and linea.startswith("bit_rate="):
                valor = linea.split("=")[1]
                if valor.isdigit():
                    audio_bitrate = int(valor)

            # Cortar si ya se obtuvieron ambos
            if fps is not None and audio_bitrate is not None:
                break

    except Exception as e:
        logging.error(f"Error al obtener información del video '{ruta}': {e}")

    return VideoInfo(fps=fps, audio_bitrate=audio_bitrate)

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

        # Condición para codificación de audio
        if info.audio_bitrate is None:
            logging.info("Bitrate de audio no detectado; se asumirá 'copy'.")
            audio_args = ["-c:a", "copy"]
        elif info.audio_bitrate > 192000:
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