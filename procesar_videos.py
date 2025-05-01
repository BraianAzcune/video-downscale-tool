import os
import sys
import logging
from datetime import datetime

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

    if not validar_rutas(rutas):
        logging.info("No se encontraron rutas válidas en el archivo. Finalizando.")
        return

    procesar_archivos(rutas)

def configurar_logging():
    fecha_log = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = f"log-{fecha_log}.log"

    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        encoding='utf-8'
    )
    logging.info("Inicio del proceso")


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
    rutas = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith('#'):
                    continue
                rutas.append(linea)
        logging.info(f"Se leyeron {len(rutas)} rutas desde el archivo.")
        return rutas
    except Exception as e:
        logging.error(f"No se pudo leer el archivo {path}: {e}")
        return []


def validar_rutas(rutas: list[str]) -> bool:
    # Valida que las rutas tengan formato correcto y existan en el sistema
    pass

def procesar_archivos(rutas: list[str]):
    # Lógica principal: por cada ruta, determinar FPS, decidir si se aplica filtro, y ejecutar ffmpeg
    pass

def guardar_fallo(path_archivo: str, mensaje: str):
    # Guarda errores específicos en un archivo de errores, si quisieras uno aparte
    pass

if __name__ == "__main__":
    main()
