from dataclasses import dataclass, field
import json
import os
import re
import subprocess
import logging
import uuid
from send2trash import send2trash

AGREGAR_SUFIJO_CONVERTED = False  # Cambiar a False para mantener el nombre original


def procesar_archivos(rutas: list[str]):
    for ruta in rutas:
        info = obtener_info_video(ruta)
        if info.fps is None:
            logging.error(f"No se pudo obtener FPS de: {ruta}")
            continue
        logging.info(f"Información extraída para '{ruta}': {info}")
        
        comando = generar_comando_ffmpeg(ruta, info)
        if comando:
            ejecutar_ffmpeg(info, comando)
            quedarse_con_mejor_archivo(info)
        else:
            logging.warning(f"Comando no generado para: {ruta}")

@dataclass
class VideoInfo:
    path: str
    nombre: str = field(init=False)
    path_salida: str = field(init=False)
    path_final: str = field(init=False)
    duration: float | None    = None
    fps: float | None = None
    audio_bitrate: int  = 0
    video_bitrate: int | None = None
    width: int | None = None
    height: int | None = None
    _last_printed_pct: int    = -1  # para seguimiento interno

    def __post_init__(self):
        # Nombre del archivo original
        self.nombre = os.path.basename(self.path)
        carpeta = os.path.dirname(self.path)
        base, ext = os.path.splitext(self.nombre)
        ext_salida = obtener_ext_salida(ext)

        base_converted = f"{base}_converted"
        salida_nombre = f"{base_converted}{ext_salida}"
        salida_ruta = os.path.join(carpeta, salida_nombre)

        if os.path.exists(salida_ruta):
            guid = uuid.uuid4().hex[:8]
            salida_nombre = f"{base_converted}_{guid}{ext_salida}"
            salida_ruta = os.path.join(carpeta, salida_nombre)
            logging.warning(f"Archivo de salida ya existe. Usando nombre alternativo: {salida_nombre}")

        self.path_salida = salida_ruta
        if AGREGAR_SUFIJO_CONVERTED:
            self.path_final = self.path_salida
        else:
            self.path_final = os.path.join(carpeta, f"{base}{ext_salida}")

    def should_print(self, pct: int) -> bool:
        return pct > self._last_printed_pct

    def update_printed_pct(self, pct: int):
        self._last_printed_pct = pct


# Auxiliar que devuelve la extensión de salida:
def obtener_ext_salida(ext_original: str) -> str:
    """
    Retorna la extensión a usar para el archivo convertido.
    Si ext_original está en la lista de contenedores compatibles con H.264, se devuelve ext_original.
    Si no, retorna '.mp4'.
    """
    contenedores_h264 = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts"}
    ext = ext_original.lower()
    return ext if ext in contenedores_h264 else ".mp4"

def obtener_info_video(ruta: str) -> VideoInfo:
    info = VideoInfo(path=ruta)

    try:
        # Pedimos también duration junto a bit_rate
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration,bit_rate",
            "-show_entries", "stream=index,codec_type,r_frame_rate,bit_rate,width,height",
            "-of", "json",
            ruta
        ]
        resultado = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )

        data = json.loads(resultado.stdout)

        # Duración en segundos
        if "duration" in data["format"]:
            info.duration = float(data["format"]["duration"])

        # Bitrate promedio total del archivo
        if "bit_rate" in data["format"]:
            info.video_bitrate = int(data["format"]["bit_rate"])

        streams = data.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if video_stream:
            # FPS
            num, denom = map(int, video_stream["r_frame_rate"].split("/"))
            info.fps = num / denom if denom else None
            # Resolución
            info.width  = video_stream.get("width")
            info.height = video_stream.get("height")

        if audio_stream and "bit_rate" in audio_stream:
            info.audio_bitrate = int(audio_stream["bit_rate"])

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


        # ④ Calcular límites de VBR (maxrate, bufsize) basados en info
        maxrate, bufsize = calcular_limites_de_bitrate(info)
        vbr_args = ["-maxrate", f"{maxrate}k", "-bufsize", f"{bufsize}k"]

        return [
            "ffmpeg",
            "-i", path,
            "-vf", filtro_vf,
            "-c:v", "h264_nvenc",
            "-preset", "p3",
            "-cq", "23",
            *vbr_args,
            *audio_args,
            info.path_salida
        ]

    except Exception as e:
        logging.error(f"Error al generar comando ffmpeg para '{path}': {e}")
        return None

def calcular_limites_de_bitrate(info: VideoInfo) -> tuple[int, int]:
    """
    Calcula maxrate y bufsize en kbps en base a:
      - El bitrate original promedio del video (con un margen del 20%)
      - Una estimación basada en la resolución (2 Mbps por megapíxel)
    Luego selecciona el menor valor como protección contra sobrecodificación.
    """
    limite_por_resolucion = None
    limite_por_bitrate = None

    if info.width and info.height:
        megapixeles = (info.width * info.height) / 1_000_000
        limite_por_resolucion = int(megapixeles * 2000)
        logging.info(f"[Resolución] {info.width}x{info.height} → {megapixeles:.2f} MPx → límite sugerido: {limite_por_resolucion} kbps")
    else:
        logging.warning("No se pudo determinar la resolución. Se omite el límite por resolución.")

    if info.video_bitrate:
        original_kbps = info.video_bitrate // 1000
        limite_por_bitrate = int(original_kbps * 1.2)
        logging.info(f"[Bitrate original] {original_kbps} kbps → límite aumentado (20%): {limite_por_bitrate} kbps")
    else:
        logging.warning("No se pudo determinar el bitrate original. Se omite el límite por bitrate.")

    if limite_por_bitrate is not None and limite_por_resolucion is not None:
        maxrate = min(limite_por_bitrate, limite_por_resolucion)
        logging.info(f"[Límite final] Usando el menor entre bitrate y resolución: {maxrate} kbps")
    elif limite_por_resolucion is not None:
        maxrate = limite_por_resolucion
        logging.info(f"[Límite final] Solo se pudo usar la resolución: {maxrate} kbps")
    elif limite_por_bitrate is not None:
        maxrate = limite_por_bitrate
        logging.info(f"[Límite final] Solo se pudo usar el bitrate original: {maxrate} kbps")
    else:
        maxrate = 2000
        logging.warning(f"[Límite final] No se pudo calcular ningún límite. Usando valor por defecto: {maxrate} kbps")

    bufsize = maxrate * 2
    logging.info(f"[Buffer] Bufsize calculado como 2x maxrate: {bufsize} kbps")

    return maxrate, bufsize



def ejecutar_ffmpeg(info: VideoInfo, comando: list[str]):
    try:
        logging.info(f"Ejecutando FFmpeg: {' '.join(comando)}")
        
        proceso = subprocess.Popen(
            comando,
            stdout=subprocess.DEVNULL,      # descartamos stdout
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        if proceso.stderr is None:
            logging.error("FFmpeg no devolvió stderr. Verifica la instalación.")
            return

        for linea in proceso.stderr:
            print_progreso(linea.strip(), info)

        codigo = proceso.wait()
        if codigo == 0:
            logging.info("Conversión completada con éxito.")
        else:
            logging.error(f"Error en la conversión. Código: {codigo}")
    
    except Exception as e:
        logging.error(f"Error al ejecutar FFmpeg: {e}")


def quedarse_con_mejor_archivo(info: VideoInfo):
    try:
        # Verifico que exista el archivo convertido
        if not os.path.exists(info.path_salida):
            logging.warning(f"No se encontró el archivo convertido en: {info.path_salida}")
            return

        size_original = os.path.getsize(info.path)
        size_convertido = os.path.getsize(info.path_salida)
        logging.info(f"[Validación] {size_convertido} > {size_original}")

        final_path = getattr(info, "path_final", info.path_salida)

        if size_convertido > size_original:
            send2trash(info.path_salida)
            if os.path.abspath(final_path) != os.path.abspath(info.path):
                if os.path.exists(final_path):
                    send2trash(final_path)
                os.rename(info.path, final_path)
                logging.info(f"Archivo original renombrado a: {final_path}")
            else:
                logging.info(f"Archivo original conservado: {info.path}")
            return

        send2trash(info.path)
        logging.info(f"Archivo original eliminado: {info.path}")

        if os.path.abspath(info.path_salida) != os.path.abspath(final_path):
            if os.path.exists(final_path):
                send2trash(final_path)
            os.rename(info.path_salida, final_path)
            logging.info(f"Archivo convertido renombrado a: {final_path}")
        else:
            logging.info(f"Archivo convertido disponible en: {final_path}")
    except Exception as e:
        logging.error(f"Error en validar_resultado para '{info.path}': {e}")

_time_pat = re.compile(r"time=(\d+):(\d+):([\d\.]+)")
def print_progreso(linea: str, info: VideoInfo):
    """
    Parsea una línea de stderr de FFmpeg, calcula porcentaje según info.duration
    y lo imprime si ha avanzado al menos 1% desde la última vez.
    """
    if info.duration is None:
        return

    m = _time_pat.search(linea)
    if not m:
        return

    horas, mins, segs = m.groups()
    elapsed = int(horas) * 3600 + int(mins) * 60 + float(segs)
    pct = int((elapsed / info.duration) * 100)

    if info.should_print(pct):
        print(f"{info.nombre} {pct}%")
        info.update_printed_pct(pct)