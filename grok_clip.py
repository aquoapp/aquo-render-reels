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


def sugiere_segunda_escena(concepto1, guion=None):
    """Cuando Ana solo da la escena 1, pide a Grok (texto) una escena 2 visual
    COHERENTE con la primera y con el guion, en el mundo estético de AQUO.
    Devuelve un string (concepto2) o None si no se pudo. Coste ínfimo.
    Usa la misma XAI_API_KEY (chat/completions), sin variables nuevas."""
    if not API_KEY:
        return None
    # Resumen del guion para dar contexto al modelo
    texto_guion = ""
    if guion:
        try:
            texto_guion = " · ".join(
                " ".join(filter(None, [e.get("l1"), e.get("l2"), e.get("l3","").replace("*","")]))
                for e in (guion if isinstance(guion, list) else [guion])
            )[:300]
        except Exception:
            texto_guion = ""
    sistema = (
        "Eres directora de arte de AQUO, marca mediterránea de bienestar (estética editorial, "
        "quiet luxury, paleta navy/marfil/arena/oliva, serena, sin personas, sin texto). "
        "Te doy la PRIMERA escena visual de un reel y debes proponer una SEGUNDA escena que "
        "CONTRASTE claramente con la primera para que el reel cambie de verdad, manteniendo el "
        "mismo mundo de marca. Reglas de contraste: si la 1 es un interior, la 2 es un exterior "
        "(o al revés); si la 1 es un plano amplio, la 2 es un primer plano de un detalle "
        "(una taza, una rama de olivo, agua, una textura); cambia el encuadre y el sujeto "
        "principal, no solo la decoración. NO repitas los mismos elementos (cama, ventana, mar) "
        "si ya están en la 1. Responde SOLO con la descripción de la segunda escena en una frase, "
        "en inglés, sin comillas ni preámbulo. Sin personas, sin caras, sin texto, sin logos.")
    usuario = f"Primera escena: {concepto1}."
    if texto_guion:
        usuario += f" Mensaje del reel: {texto_guion}."
    usuario += " Dame la segunda escena."

    payload = json.dumps({
        "model": os.environ.get("GROK_MODELO_TEXTO", "grok-4.3"),
        "messages": [
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario},
        ],
        "temperature": 0.8,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(f"{BASE}/chat/completions", data=payload,
                                     method="POST", headers=_headers())
        with urllib.request.urlopen(req, timeout=40) as r:
            data = json.loads(r.read())
        txt = data["choices"][0]["message"]["content"].strip().strip('"').strip()
        if txt:
            _log("escena 2 sugerida por IA:", txt[:80])
            return txt
    except Exception as e:
        _log("no se pudo sugerir escena 2 (sigo con 1):", repr(e))
    return None


def genera_clips(orden, medidor=None):
    """Capa 3 multi-clip: genera N clips (uno por 'concepto' de la lista).
    Devuelve una LISTA de URLs (las que se hayan podido generar).

    Campos de la orden:
      · conceptos  : lista de descripciones, una por clip (modo A). Si no viene,
                     usa [concepto] (compatibilidad con un solo clip).
      · movimientos: lista opcional de movimientos, emparejada con conceptos.
      · imagenes_url: lista opcional de imágenes tuyas (modo B), una por clip.
      · duracion   : segundos por clip (def 6).

    Degradación: si un clip falla, se omite y se sigue con los demás. Si NINGUNO
    sale, devuelve [] y el motor caerá al banco."""
    duracion = int(orden.get("duracion") or 6)
    conceptos = orden.get("conceptos")
    movimientos = orden.get("movimientos") or []
    imagenes = orden.get("imagenes_url") or []

    # Normalizo a listas de igual criterio (compatibilidad con campo singular)
    if not conceptos:
        c = orden.get("concepto")
        conceptos = [c] if c else []
    if not imagenes and orden.get("imagen_url"):
        imagenes = [orden.get("imagen_url")]

    # ── Inteligencia: si solo hay 1 concepto pero el guion tiene varias escenas,
    #    pido a la IA una segunda escena coherente (a menos que se desactive). ──
    auto2 = orden.get("auto_escena2", True)
    guion = orden.get("guion")
    nesc_guion = len(guion) if isinstance(guion, list) else 1
    if auto2 and len(conceptos) == 1 and not imagenes and nesc_guion >= 2:
        c2 = sugiere_segunda_escena(conceptos[0], guion)
        if c2:
            conceptos = [conceptos[0], c2]
            _log("completada escena 2 automáticamente para no enganchar")

    n = max(len(conceptos), len(imagenes), 1)
    urls = []
    for i in range(n):
        sub = {
            "concepto": conceptos[i] if i < len(conceptos) else (conceptos[-1] if conceptos else None),
            "movimiento": movimientos[i] if i < len(movimientos) else orden.get("movimiento"),
            "imagen_url": imagenes[i] if i < len(imagenes) else None,
            "duracion": duracion,
        }
        try:
            urls.append(genera_clip(sub, medidor=medidor))
            _log(f"clip {i+1}/{n} listo")
        except Exception as e:
            _log(f"clip {i+1}/{n} falló, lo omito:", repr(e))
    return urls
