# -*- coding: utf-8 -*-
"""
AQUO · Capa de narración IRIS (voz de marca).

Capa AISLADA y OPCIONAL. No toca el render visual.
Flujo: el MP4 ya montado (mudo) + el texto a narrar → genera voz con
ElevenLabs → mezcla la voz en el MP4 → devuelve un MP4 nuevo con audio.

Principio "no humo": si algo falla (falta clave, API caída, texto vacío),
NO rompe el reel. Devuelve el MP4 original mudo y deja constancia en el log.
El reel siempre sale; como mucho, sale sin voz.

Variables de entorno necesarias (se ponen en Render, nunca en el chat):
  · ELEVENLABS_API_KEY   → clave de la cuenta de ElevenLabs
  · ELEVENLABS_VOICE_ID  → id de la voz elegida para IRIS
  · ELEVENLABS_MODEL     → opcional; por defecto eleven_multilingual_v2 (ES nativo)
"""
import os, subprocess, tempfile, time, urllib.request, urllib.error, json

def _log(*a): print("[voz_iris]", *a, flush=True)

API_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")
MODEL    = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")

# Ajustes de voz: serena, cálida, estable. IRIS acompaña, no locuta.
VOICE_SETTINGS = {
    "stability": 0.55,          # más alto = más calmada y consistente
    "similarity_boost": 0.80,   # fidelidad al timbre de la voz elegida
    "style": 0.15,              # poca exageración: tono editorial, no comercial
    "use_speaker_boost": True,
}


def _dur(path):
    """Duración en segundos de un archivo de media (vídeo o audio)."""
    out = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True).stdout.strip()
    try: return float(out)
    except Exception: return 0.0


def _genera_voz(texto, dest_mp3):
    """Llama a ElevenLabs TTS y guarda el MP3. Lanza excepción si falla."""
    if not API_KEY:  raise RuntimeError("falta ELEVENLABS_API_KEY")
    if not VOICE_ID: raise RuntimeError("falta ELEVENLABS_VOICE_ID")
    texto = (texto or "").strip()
    if not texto:    raise RuntimeError("texto de narración vacío")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    payload = json.dumps({
        "text": texto,
        "model_id": MODEL,
        "voice_settings": VOICE_SETTINGS,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "xi-api-key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    })
    with urllib.request.urlopen(req, timeout=90) as r, open(dest_mp3, "wb") as fh:
        fh.write(r.read())
    sz = os.path.getsize(dest_mp3)
    if sz < 512:
        raise RuntimeError(f"audio devuelto demasiado pequeño ({sz} bytes)")
    _log("voz generada:", sz, "bytes")
    return dest_mp3


def _mezcla(video_mudo, voz_mp3, salida):
    """Monta la voz sobre el vídeo. El VÍDEO manda la duración: la voz entra con
    una pequeña pausa inicial y, si fuera más larga que el vídeo, se corta; si es
    más corta, el resto del vídeo queda en silencio. El vídeo nunca se acorta."""
    dur_video = _dur(video_mudo)
    # 0.4s de respiro antes de que arranque la voz; audio acotado a la duración del vídeo
    subprocess.run([
        "ffmpeg","-hide_banner","-loglevel","error","-y",
        "-i", video_mudo,
        "-i", voz_mp3,
        "-filter_complex", "[1:a]adelay=400|400,volume=1.0[a]",
        "-map","0:v:0","-map","[a]",
        "-c:v","copy",            # el vídeo NO se recodifica: idéntico al original
        "-c:a","aac","-b:a","160k",
        "-t", f"{dur_video:.3f}", # la salida dura lo que el vídeo, ni más ni menos
        "-movflags","+faststart",
        salida,
    ], check=True)
    return salida


def aplica_narracion(video_path, texto):
    """Punto de entrada. Devuelve (ruta_video_final, n_caracteres).

    - Si la narración se genera y mezcla bien → (MP4 con voz, nº de caracteres narrados).
    - Si algo falla → (video_path original mudo, 0), sin romper nada.
    """
    n_chars = len((texto or "").strip())
    try:
        tmp_mp3 = os.path.join(tempfile.gettempdir(), f"iris_voz_{int(time.time())}.mp3")
        _genera_voz(texto, tmp_mp3)
        salida = video_path.replace(".mp4", "_voz.mp4")
        if salida == video_path:
            salida = video_path + "_voz.mp4"
        _mezcla(video_path, tmp_mp3, salida)
        try: os.remove(tmp_mp3)
        except OSError: pass
        _log("narración aplicada:", os.path.basename(salida),
             f"(vídeo {_dur(video_path):.1f}s · {n_chars} caracteres)")
        return salida, n_chars
    except urllib.error.HTTPError as e:
        cuerpo = ""
        try: cuerpo = e.read().decode("utf-8", "ignore")[:200]
        except Exception: pass
        _log("ElevenLabs HTTP", e.code, "-> reel sin voz.", cuerpo)
        return video_path, 0
    except Exception as e:
        _log("narración no aplicada (reel sale mudo):", repr(e))
        return video_path, 0
