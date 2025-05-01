import os
import subprocess
import logging
import uuid

def procesar_archivos(rutas: list[str]):
    for ruta in rutas:
        fps = obtener_fps(ruta)
        if fps is None:
            logging.error(f"No se pudo obtener FPS de: {ruta}")
            continue
        logging.info(f"FPS obtenidos para '{ruta}': {fps:.2f}")
        
        comando = generar_comando_ffmpeg(ruta, fps)
        if comando:
            ejecutar_ffmpeg(comando)
        else:
            logging.warning(f"Comando no generado para: {ruta}")

def obtener_fps(ruta: str) -> float | None:
    try:
        resultado = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=r_frame_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                ruta
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        fps_str = resultado.stdout.strip()  # Ej: "60/1" o "30000/1001"
        if "/" in fps_str:
            num, denom = map(int, fps_str.split("/"))
            return num / denom if denom != 0 else None
        return float(fps_str)

    except Exception as e:
        logging.error(f"Error al obtener FPS de '{ruta}': {e}")
        return None


def generar_comando_ffmpeg(path: str, fps: float) -> list[str] | None:
    """
    Genera el comando ffmpeg para convertir el video a 480p usando el encoder h264_nvenc.
    
    - Si los FPS del video original son mayores a 40, se fuerza la reducción a 30 FPS.
    - Si son 40 o menos, se mantiene la tasa original y no se aplica el filtro fps.
    - Si el archivo de salida ya existe, se agrega un sufijo único con un GUID para evitar sobrescritura.
    
    El archivo de salida queda en la misma carpeta que el original, con sufijo '_converted[_guid].ext'.
    
    Parámetros:
        path (str): Ruta absoluta al archivo de video original.
        fps (float): FPS promedio detectado del video original.
    
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
        if fps > 40:
            filtros.append("fps=30")

        filtro_vf = ",".join(filtros)

        return [
            "ffmpeg",
            "-i", path,
            "-vf", filtro_vf,
            "-c:v", "h264_nvenc",
            "-preset", "p3",
            "-cq", "23",
            "-c:a", "copy",
            path_salida
        ]
    except Exception as e:
        logging.error(f"Error al generar comando ffmpeg para '{path}': {e}")
        return None

def ejecutar_ffmpeg(comando: list[str]):
    # Ejecuta el comando ffmpeg con subprocess y loguea resultado
    pass
