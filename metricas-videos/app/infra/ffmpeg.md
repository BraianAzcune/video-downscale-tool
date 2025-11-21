# Reporte de comandos ffprobe

## Datos generales del archivo

```powershell
ffprobe -v error -show_entries format=duration,format_name,bit_rate -of json "D:\OBS-RECORDS\2024-12-20 01-13-34 talos este nivel me describe.mkv"
```

```json
{
    "format": {
        "format_name": "matroska,webm",
        "duration": "12.167000",
        "bit_rate": "37200199"
    }
}
```

## Datos del stream de video

```powershell
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,bit_rate,width,height,avg_frame_rate,r_frame_rate,pix_fmt,profile,level,color_space,color_transfer,color_primaries -of json "D:\OBS-RECORDS\2024-12-20 01-13-34 talos este nivel me describe.mkv"
```

```json
{
    "streams": [
        {
            "codec_name": "h264",
            "profile": "High",
            "width": 1920,
            "height": 1080,
            "pix_fmt": "yuv420p",
            "level": 42,
            "color_space": "bt709",
            "color_transfer": "bt709",
            "color_primaries": "bt709",
            "r_frame_rate": "60/1",
            "avg_frame_rate": "60/1"
        }
    ]
}
```

## Datos de los streams de audio

```powershell
ffprobe -v error -select_streams a -show_entries stream=index,codec_name,bit_rate,channels,sample_rate,channel_layout -of json "D:\OBS-RECORDS\2024-12-20 01-13-34 talos este nivel me describe.mkv"
```

```json
{
    "streams": [
        {
            "index": 1,
            "codec_name": "aac",
            "sample_rate": "48000",
            "channels": 2,
            "channel_layout": "stereo"
        },
        {
            "index": 2,
            "codec_name": "aac",
            "sample_rate": "48000",
            "channels": 2,
            "channel_layout": "stereo"
        },
        {
            "index": 3,
            "codec_name": "aac",
            "sample_rate": "48000",
            "channels": 2,
            "channel_layout": "stereo"
        }
    ]
}
```

## Fallbacks útiles cuando faltan bitrates

Bitrate total aproximado si `format.bit_rate` no está presente:

```
bitrate_total_bps ≈ (size_bytes * 8) / duracion_seg
```

Debe existir un atributo indicando si se utilizó este método de estimación.

## Mapeo de datos

### VideoArchivoDTO

* ruta → del escaneo (Path)
* size_bytes → filesystem (Path.stat().st_size)
* fecha_modificacion → filesystem (Path.stat().st_mtime → datetime)
* duracion_seg → format.duration (primer comando)
* contenedor → format.format_name (primer comando)

### VideoStreamDTO (v:0)

* codec ← streams[0].codec_name
* bitrate_bps ← streams[0].bit_rate (None si falta)
* width, height ← directos
* fps ← avg_frame_rate convertido (ej. "60/1" → 60.0)
* pix_fmt, profile, level ← directos
* color_space, color_transfer, color_primaries ← directos
* es_hdr ← True si color_transfer ∈ {smpte2084, arib-std-b67} o color_primaries == bt2020
* es_vfr ← True si avg_frame_rate ≠ r_frame_rate

### AudioStreamDTO

Por cada stream de audio:

* codec ← codec_name (ej. aac)
* bitrate_bps ← bit_rate (None si falta)
* channels ← channels
* sample_rate ← sample_rate
* layout ← channel_layout (opcional)

## Bandera de estimación de bitrate

* bitrate_es_estimado: bool
  True si se usó el cálculo `size_bytes*8/duracion_seg` o `format.bit_rate` como aproximación.
