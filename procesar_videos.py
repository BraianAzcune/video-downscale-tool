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
    log_file = f"log-{fecha_log}.txt"

    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        encoding='utf-8'
    )
    logging.info("Inicio del proceso")


def archivo_existe(path: str) -> bool:
    # Verifica si existe el archivo
    pass

def crear_archivo_vacio(path: str):
    # Crea un archivo de texto vacío para que el usuario lo complete
    pass

def leer_rutas_desde_archivo(path: str) -> list[str]:
    # Lee líneas del archivo de texto, las limpia y devuelve como lista
    pass

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
