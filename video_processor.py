import subprocess
import logging

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
    # Genera el comando ffmpeg a ejecutar (como lista de args)
    pass

def ejecutar_ffmpeg(comando: list[str]):
    # Ejecuta el comando ffmpeg con subprocess y loguea resultado
    pass
