import os
import logging
from video_processor import procesar_archivos
from logger_config import configurar_logging

def main():
    configurar_logging()
    archivo = "archivos_a_transformar.txt"
    
    if not archivo_existe(archivo):
        crear_archivo_vacio(archivo)
        logging.info("Archivo de entrada no encontrado. Se creó uno nuevo. Finalizando.")
        return

    rutas = leer_rutas_desde_archivo(archivo)
    
    if not rutas:
        logging.info("El archivo está vacío. Finalizando.")
        return

    rutas = remove_duplicate_paths(rutas)
    rutas = filter_valid_paths(rutas)
    rutas = filter_supported_extensions(rutas)

    if len(rutas) == 0:
        logging.info("No se encontraron rutas válidas. Finalizando.")
        return

    procesar_archivos(rutas)

def archivo_existe(path: str) -> bool:
    return os.path.isfile(path)


def crear_archivo_vacio(path: str):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# Agregá acá los paths absolutos a los videos que querés procesar\n")
        logging.info(f"Archivo vacío creado: {path}")
    except Exception as e:
        logging.error(f"No se pudo crear el archivo {path}: {e}")


def leer_rutas_desde_archivo(path: str) -> list[str]:
    rutas: list[str] = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith('#'):
                    continue
                linea = remover_comillas_dobles_extremos(linea)
                rutas.append(linea)
        logging.info(f"Se leyeron {len(rutas)} rutas desde el archivo.")
        return rutas
    except Exception as e:
        logging.error(f"No se pudo leer el archivo {path}: {e}")
        return []


def remover_comillas_dobles_extremos(texto: str) -> str:
    if texto.startswith('"') and texto.endswith('"'):
        return texto[1:-1]
    return texto

def filter_valid_paths(rutas: list[str]) -> list[str]:
    rutas_validas: list[str] = []

    for ruta in rutas:
        if os.path.isfile(ruta):
            rutas_validas.append(ruta)
        else:
            logging.warning(f"Ruta inválida o archivo no encontrado: {ruta}")

    logging.info(f"Se encontraron {len(rutas_validas)} / {len(rutas)} rutas válidas")
    return rutas_validas

def filter_supported_extensions(rutas: list[str]) -> list[str]:
    extensiones_validas = {'.wmv', '.webm', '.mp4', '.mkv'}
    rutas_filtradas: list[str] = []

    for ruta in rutas:
        ext = os.path.splitext(ruta)[1].lower()
        if ext in extensiones_validas:
            rutas_filtradas.append(ruta)
        else:
            logging.warning(f"Extensión no soportada: {ruta}")

    logging.info(f"{len(rutas_filtradas)} archivos tienen extensiones válidas.")
    return rutas_filtradas


def remove_duplicate_paths(rutas: list[str]) -> list[str]:
    rutas_unicas = list(dict.fromkeys(rutas))
    if len(rutas_unicas) < len(rutas):
        logging.info(f"Se eliminaron {len(rutas) - len(rutas_unicas)} rutas duplicadas.")
    return rutas_unicas


def guardar_fallo(path_archivo: str, mensaje: str):
    # Guarda errores específicos en un archivo de errores, si quisieras uno aparte
    pass

if __name__ == "__main__":
    main()
