# Metricas Videos

Pipeline en Python para auditar colecciones de videos usando ffprobe/ffmpeg y exportar métricas a Excel.

## Objetivo del proyecto

El objetivo final de esta aplicación es obtener una visión cuantitativa y objetiva de una colección de videos.
A través de la extracción de métricas técnicas (duración, resolución, bitrate, fps, formato, audio, etc.) y su consolidación en un archivo Excel, permite:

* Identificar videos que presentan un tamaño desproporcionado respecto a su duración o resolución.
* Detectar formatos o códecs ineficientes que podrían recomprimirse.
* Analizar la relación entre calidad visual, peso y parámetros de codificación.
* Evaluar el impacto del audio en el tamaño total del archivo.
* Facilitar decisiones de optimización y normalización dentro de la galería.

En síntesis, la aplicación busca servir como herramienta de auditoría y diagnóstico para mantener una colección de videos eficiente, equilibrada y con una calidad coherente con su propósito.


## Workflow
1. Escanea la carpeta raíz (`raiz_media`) y lista todos los archivos de video admitidos.
2. Aplica exclusiones definidas en `exclusiones.txt` (rutas o patrones).
3. Extrae metadata con ffprobe y construye DTOs unificados.
4. Calcula métricas derivadas (MB/min, bitrate estimado, bits/pixel/frame) y agrupa por bucket `resolución@fps`.
5. Marca outliers comparando cada video con el promedio de su bucket.
6. Genera un Excel con detalle por video y resumen por bucket para facilitar decisiones de recompressión.

## Config
- Python 3.11+
- ffprobe / ffmpeg disponibles en PATH o definidos vía `ffprobe_bin`, `ffmpeg_bin`.
- Configuración vía formato propio en settings.txt

## Próximos pasos
- Implementar cada servicio respetando los contratos definidos.
- Añadir pruebas unitarias para repositories y servicios críticos.
