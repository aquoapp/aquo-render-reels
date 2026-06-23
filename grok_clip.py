# -*- coding: utf-8 -*-
"""
AQUO · Capa 3 — clips de metraje a medida con Grok (xAI Imagine API).

Genera un clip de vídeo NUEVO para vestir de AQUO. Dos modos:
  · MODO A (todo nuevo): Grok crea la imagen base 9:16 on-brand → la anima a vídeo.
  · MODO B (tu imagen):  partes de una imagen tuya (URL) → Grok solo la anima.

Devuelve la URL del vídeo generado (clipUrl), que el motor mete en la capa 2
(texto + marca + voz). Capa AISLADA: si Grok falla, el motor cae al banco.

Endpoints verificados (xAI docs, jun 2026):
  · Imagen: POST https://api.x.ai/v1/images/generations  (grok-imagine-image-quality)
  · Vídeo:  POST https://api.x.ai/v1/videos/generations   (grok-imagine-video-1.5, async)
            GET  https://api.x.ai/v1/videos/{request_id}   → status: done → video.url

Variables de entorno (en Render, nunca en el chat):
  · XAI_API_KEY            clave de xAI
  · GROK_MODELO_IMAGEN     opcional (def grok-imagine-image-quality)
  · GROK_MODELO_VIDEO      opcional (def grok-imagine-video-1.5)
"""
import os, time, json, urllib.request, urllib.error

def _log(*a): print("[grok_clip]", *a, flush=True)

API_KEY = os.environ.get("XAI_API_KEY", "")
BASE = "https://api.x.ai/v1"
MOD_IMG = os.environ.get("GROK_MODELO_IMAGEN", "grok-imagine-image-quality")
MOD_VID = os.environ.get("GROK_MODELO_VIDEO", "grok-imagine-video-1.5")

# Prompt maestro de imagen base: blinda la marca. SIN personas, SIN texto, SIN logos.
PLANTILLA_IMAGEN = (
    "Mediterranean editorial still life, {concepto}, "
    "soft natural morning light, serene quiet-luxury aesthetic, "
    "muted palette of deep navy, ivory, warm sand and olive green, "
    "shallow depth of field, generous empty negative space in the upper two thirds, "
    "calm and minimal, photographic, vertical 9:16 composition. "
    "No people, no faces, no hands, no text, no words, no logos, no watermarks."
)
# Prompt de movimiento: sutil, meditativo, cámara quieta.
PLANTILLA_MOVIMIENTO = (
    "Very subtle gentle motion only: {movimiento}. "
    "Static camera, no zoom, no pan, no people appearing. "
    "Serene, slow, meditative, seamless and loopable."
)


def _headers():
    if not API_KEY:
        raise RuntimeError("falta XAI_API_KEY en el entorno")
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def genera_imagen(concepto, aspect_ratio="9:16"):
    """MODO A · paso 1: imagen base on-brand. Devuelve la URL de la imagen."""
    prompt = PLANTILLA_IMAGEN.format(concepto=concepto)
    payload = json.dumps({
        "model": MOD_IMG,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/images/generations", data=payload,
                                 method="POST", headers=_headers())
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read())
    url = (data.get("data") or [{}])[0].get("url")
    if not url:
        raise RuntimeError(f"Grok no devolvió URL de imagen: {str(data)[:200]}")
    _log("imagen base generada")
    return url


def anima_imagen(image_url, movimiento, duracion=6):
    """Anima una imagen a vídeo (modo A paso 2, o modo B). Devuelve (video_url, segundos).
    Asíncrono: lanza la tarea y sondea hasta done. Tope de espera defensivo."""
    prompt = PLANTILLA_MOVIMIENTO.format(movimiento=movimiento or "light shifts slowly")
    payload = json.dumps({
        "model": MOD_VID,
        "prompt": prompt,
        "image": {"url": image_url},
        "duration": int(duracion),
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/videos/generations", data=payload,
                                 method="POST", headers=_headers())
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    request_id = data.get("request_id") or data.get("id")
    if not request_id:
        raise RuntimeError(f"Grok no devolvió request_id de vídeo: {str(data)[:200]}")
    _log("animación lanzada:", request_id, "— sondeando...")

    # Sondeo: cada 5s, hasta ~4 min (la animación suele tardar 1-2 min).
    espera_max = int(os.environ.get("GROK_VIDEO_TIMEOUT", "240"))
    t0 = time.time()
    while time.time() - t0 < espera_max:
        time.sleep(5)
        g = urllib.request.Request(f"{BASE}/videos/{request_id}", headers=_headers())
        with urllib.request.urlopen(g, timeout=30) as rr:
            res = json.loads(rr.read())
        estado = (res.get("status") or "").lower()
        if estado in ("done", "completed"):
            vid = (res.get("video") or {}).get("url") or res.get("url")
            if not vid:
                raise RuntimeError("Grok dijo done pero sin video.url")
            _log("vídeo listo tras", int(time.time() - t0), "s")
            return vid, int(duracion)
        if estado in ("failed", "error", "expired"):
            raise RuntimeError(f"Grok falló la animación: {estado} · {str(res)[:200]}")
    raise RuntimeError(f"Grok no terminó el vídeo en {espera_max}s (timeout)")


def genera_clip(orden, medidor=None):
    """Punto de entrada de la capa 3. Lee la orden y devuelve la URL del clip,
    o None si no se pudo (el motor caerá entonces al banco).

    Campos de la orden (capa 3):
      · concepto    (modo A): qué mostrar, ej "still water at dawn near olive branches"
      · movimiento  : descripción del movimiento sutil (opcional)
      · imagen_url  (modo B): si viene, se salta la generación de imagen y se anima esa
      · duracion    : segundos del clip (def 6)

    Si se pasa `medidor`, apunta los costes de Grok (imagen y/o vídeo)."""
    duracion = int(orden.get("duracion") or 6)
    movimiento = orden.get("movimiento") or "water ripples softly, light shifts slowly"

    imagen_url = orden.get("imagen_url") or orden.get("image_url")
    if not imagen_url:
        # MODO A: generar imagen base
        concepto = orden.get("concepto") or "still mediterranean water at calm dawn"
        imagen_url = genera_imagen(concepto)
        if medidor: medidor.grok_imagen(1)

    video_url, segs = anima_imagen(imagen_url, movimiento, duracion)
    if medidor: medidor.grok_video(segs)
    return video_url
