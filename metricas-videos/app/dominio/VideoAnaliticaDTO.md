## CAMPOS calculados de VideoAnaliticaDTO

### 1) `mb_por_minuto`

* **Para qué sirve:** compara “tamaño relativo al tiempo”. Es un proxy simple y muy legible para detectar outliers sin abrir debate técnico.
* **Fórmula:**
  `MB/min = (size_bytes / 1024^2) / (duracion_seg / 60)`
* **Alertas:** en clips muy cortos (<30 s) se dispara; marcá como “no concluyente” o aplicá un mínimo de duración.
* **Ejemplo (tu video):** ~**2.00 MB/min** → razonable para 480p@30 con H.264 + AAC.

### 2) `bitrate_total_estimado` **(con fallback robusto)**

* **Para qué sirve:** es la métrica madre para comparar pesos, y para validar consistencia con el tamaño del archivo.
* **Fórmula recomendada (en orden):**

  1. `format.bit_rate` de ffprobe si está presente;
  2. si no, **suma** `video.bit_rate + Σ audio.bit_rate`;
  3. si no, **estimar**: `(size_bytes * 8) / duracion_seg`.
* **Alertas:** contenedores rara vez informan overhead; esperá ~1–3% de diferencia.
* **Ejemplo:** video 142,733 bps + audio 128,001 bps → **~270,734 bps**.
  Estimación por tamaño: 7.68 MB en 230.53 s ≈ **266–275 kbps** (consistente).

### 3) `bits_por_pixel_frame` (bppf) 

* **Para qué sirve:** normaliza bitrate por **resolución** y **fps**. Es la métrica técnica más útil para “eficiencia de compresión”.
* **Fórmula:** `bppf = video_bitrate_bps / (width * height * fps)`
* **Reglas de dedo (H.264 SDR):**
  ~0.05–0.10 bppf (buena calidad SD/HD ligera),
  <0.02: visible compresión fuerte / material simple,

  > 0.15: quizá sobrecomprimido al revés (bitrate alto) o contenido difícil.
* **Alertas:** VFR extrema y escenas muy estáticas pueden sesgar.
* **Ejemplo:** **0.0116 bppf** → muy bajo (contenido probablemente simple: letras/lyrics 480p@30).

### 4) `flags_contexto` ✅ **Mantener (tipado con Enum)**

* **Para qué sirve:** justifica por qué algo fue marcado (transparencia para decidir recomprimir o no).
* **Valores permitidos (Enum `FlagContexto`):**

  * `"OUTLIER_FUERTE"`, `"OUTLIER_SUAVE"`,
  * `"MUY_CORTO"`, `"DURACION_CORTA"`,
  * `"AUDIO_DOMINANTE"`,
  * `"VFR"`, `"HDR"`,
  * `"BITRATE_CONTAINER_FALTANTE"`,
  * `"BUCKET_PEQUENO"`.
* **Notas:** evitar duplicados (usar `set` si aplica), y registrar siempre la causa que disparó la marca.

### 5) `kbps_total` ✅ **(legibilidad para Excel)**

* **Para qué sirve:** versión amigable de `bitrate_total_estimado` para lectura rápida y tablas.
* **Cálculo recomendado:**

  * `kbps_total = round(bitrate_total_estimado / 1000)` cuando `bitrate_total_estimado` no es `None`.
* **Alertas:** si `bitrate_total_estimado` fue estimado por tamaño/tiempo, agregar flag `"BITRATE_CONTAINER_FALTANTE"`.

### 6) `kbps_video` ✅ **(diagnóstico específico de video)**

* **Para qué sirve:** aislar el aporte del **video** al bitrate total (útil para comparar con `bppf`).
* **Cálculo recomendado:**

  * Si `stream_video.bitrate_bps` existe → `kbps_video = round(stream_video.bitrate_bps / 1000)`.
  * Si no existe, no estimar a ciegas; dejar `None` y apoyarse en `kbps_total`.
* **Alertas:** distintos contenedores/ffprobe a veces omiten `bitrate_bps` de video.

### 7) `audio_share_pct` ✅ **(peso relativo del audio)**

* **Para qué sirve:** detectar casos donde el audio domina (p. ej., música/podcast o video sobrecomprimido).
* **Cálculo recomendado:**

  * `audio_share_pct = 100 * (Σ audio.bitrate_bps válidos) / bitrate_total_estimado`.
* **Umbrales sugeridos:**

  * `> 40%` → marcar `"AUDIO_DOMINANTE"`.
  * `> 60%` → revisar mezcla/canal o redundancias (pistas duplicadas).
* **Alertas:** si falta `bitrate_total_estimado` o no hay `bitrate_bps` en audio, dejar `None` y no marcar.


### 8) `duracion_categoria` ✅ **(control de falsos positivos)**

* **Para qué sirve:** contextualiza métricas sensibles a clips cortos (`MB/min`).
* **Clasificación recomendada:**

  * **MUY CORTO:** `< 10 s`
  * **CORTO:** `10–120 s`
  * **MEDIO:** `120–300 s`
  * **LARGO:** `> 300 s`

### 9) `bucket_resolucion_fps`

* **Para qué sirve:** agrupa para comparar “peras con peras”.
* **Clave mejorada:**
  `"{alto_norm}p@{fps_norm}{'/HDR' si es_hdr}{'/' + codec si querés granularidad}"`

  * **alto_norm:** 360/480/720/1080 etc.
  * **fps_norm:** 24/25/30/50/60 (redondeo al vecino).
  * Opcional: incluir **HDR** y/o **codec** cuando tengas mezcla heterogénea.
* **Ejemplo:** **"480p@30/H264"** (SDR).

### 10) `ratio_vs_promedio_bucket` ✅ **(usar mediana/MAD)**

* **Para qué sirve:** señal de outlier “dentro del bucket”.
* **Cálculo recomendado:**

  * Usar **mediana** del bucket (no promedio) de `mb_por_minuto` o `bppf`.
  * `ratio = valor / mediana_bucket`.
  * Para flag: `z = (valor - mediana) / (1.4826 * MAD)` y marcar si `|z| ≥ 3`.
* **Alertas:** buckets con <5 items: poné “confianza baja”.