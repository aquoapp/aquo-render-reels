# -*- coding: utf-8 -*-
"""
AQUO · Capa de narración IRIS (voz de marca).

Capa AISLADA y OPCIONAL. No toca el render visual.
Flujo: el MP4 ya montado (mudo) + el texto a narrar → genera voz con
ElevenLabs → mezcla la voz en el MP4 → devuelve un MP4 nuevo con audio.

REPARTO TEMPORAL (jun 2026)
---------------------------
Antes, IRIS decia todo el texto de golpe al principio y el reel seguia
mudo el resto. Eso pasaba porque el texto llegaba como UN solo bloque y se
pegaba al segundo 0. Ahora:

  - Si el texto trae el separador "|"  ->  son DOS piezas: HOOK | CIERRE.
    El HOOK arranca al principio (0.4 s) y el CIERRE se ANCLA al final del
    video (termina ~0.3 s antes del corte, sobre la escena del remate a bio).
    En medio: silencio respirado. IRIS abre y cierra; el centro deja ver.

  - Si NO trae separador (narracion completa, o textos antiguos)  ->  se
    comporta EXACTAMENTE como antes: una sola pieza con 0.4 s de respiro.
    Cero regresion.

Principio "no humo": si algo falla (falta clave, API caida, texto vacio),
NO rompe el reel. Devuelve el MP4 original mudo y deja constancia en el log.

Variables de entorno (se ponen en Render, nunca en el chat):
  - ELEVENLABS_API_KEY   -> clave de la cuenta de ElevenLabs
  - ELEVENLABS_VOICE_ID  -> id de la voz elegida para IRIS
  - ELEVENLABS_MODEL     -> opcional; por defecto eleven_multilingual_v2
"""
import os, subprocess, tempfile, time, urllib.request, urllib.error, json

def _log(*a): print("[voz_iris]", *a, flush=True)

API_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")
MODEL    = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")

# Separador que el panel usa para marcar el corte HOOK | CIERRE.
SEP = "|"

# Respiros (segundos)
ENTRADA_HOOK  = 0.40   # el hook no entra pegado al frame 0
COLCHON_FINAL = 0.30   # el cierre termina un pelin antes del corte de video
SUELO_HUECO   = 1.20   # hueco minimo de silencio entre hook y cierre

# Ajustes de voz: serena, calida, estable. IRIS acompana, no locuta.
VOICE_SETTINGS = {
    "stability": 0.55,
    "similarity_boost": 0.80,
    "style": 0.15,
    "use_speaker_boost": True,
}


def _dur(path):
    """Duracion en segundos de un archivo de media (video o audio)."""
    out = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True).stdout.strip()
    try: return float(out)
    except Exception: return 0.0


def _genera_voz(texto, dest_mp3):
    """Llama a ElevenLabs TTS y guarda el MP3. Lanza excepcion si falla."""
    if not API_KEY:  raise RuntimeError("falta ELEVENLABS_API_KEY")
    if not VOICE_ID: raise RuntimeError("falta ELEVENLABS_VOICE_ID")
    texto = (texto or "").strip()
    if not texto:    raise RuntimeError("texto de narracion vacio")

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
        raise RuntimeError(f"audio devuelto demasiado pequeno ({sz} bytes)")
    _log("voz generada:", sz, "bytes")
    return dest_mp3


def _mezcla_simple(video_mudo, voz_mp3, salida):
    """Una sola pieza de voz, con respiro inicial. Comportamiento CLASICO.
    El video manda la duracion y nunca se acorta."""
    dur_video = _dur(video_mudo)
    ms = int(ENTRADA_HOOK * 1000)
    subprocess.run([
        "ffmpeg","-hide_banner","-loglevel","error","-y",
        "-i", video_mudo,
        "-i", voz_mp3,
        "-filter_complex", f"[1:a]adelay={ms}|{ms},volume=1.0[a]",
        "-map","0:v:0","-map","[a]",
        "-c:v","copy",
        "-c:a","aac","-b:a","160k",
        "-t", f"{dur_video:.3f}",
        "-movflags","+faststart",
        salida,
    ], check=True)
    return salida


def _mezcla_repartida(video_mudo, hook_mp3, cierre_mp3, salida):
    """DOS piezas de voz en el timeline:
       - HOOK   -> entra a ENTRADA_HOOK (0.4 s), sobre la apertura.
       - CIERRE -> se ancla al FINAL: termina COLCHON_FINAL (0.3 s) antes del
                   corte de video, sobre la escena del remate a bio.
       Entre ambos queda silencio. El video manda la duracion.
       Si el video es demasiado corto para separarlas, cae con elegancia a
       la mezcla simple concatenada (nunca peor que antes)."""
    dur_video  = _dur(video_mudo)
    dur_hook   = _dur(hook_mp3)
    dur_cierre = _dur(cierre_mp3)

    necesario = ENTRADA_HOOK + dur_hook + SUELO_HUECO + dur_cierre + COLCHON_FINAL
    if dur_video < necesario:
        _log(f"video {dur_video:.1f}s corto para reparto (necesita {necesario:.1f}s) "
             f"-> mezcla simple concatenada")
        unido = hook_mp3.replace(".mp3", "_unido.mp3")
        subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error","-y",
            "-i", hook_mp3, "-i", cierre_mp3,
            "-filter_complex","[0:a][1:a]concat=n=2:v=0:a=1[a]",
            "-map","[a]", unido,
        ], check=True)
        r = _mezcla_simple(video_mudo, unido, salida)
        try: os.remove(unido)
        except OSError: pass
        return r

    inicio_cierre = dur_video - COLCHON_FINAL - dur_cierre
    ms_hook   = int(ENTRADA_HOOK * 1000)
    ms_cierre = int(inicio_cierre * 1000)

    _log(f"reparto IRIS - hook@{ENTRADA_HOOK:.2f}s ({dur_hook:.1f}s) - "
         f"cierre@{inicio_cierre:.2f}s ({dur_cierre:.1f}s) - video {dur_video:.1f}s")

    filtro = (
        f"[1:a]adelay={ms_hook}|{ms_hook},volume=1.0[h];"
        f"[2:a]adelay={ms_cierre}|{ms_cierre},volume=1.0[c];"
        f"[h][c]amix=inputs=2:duration=longest:normalize=0[a]"
    )
    subprocess.run([
        "ffmpeg","-hide_banner","-loglevel","error","-y",
        "-i", video_mudo,
        "-i", hook_mp3,
        "-i", cierre_mp3,
        "-filter_complex", filtro,
        "-map","0:v:0","-map","[a]",
        "-c:v","copy",
        "-c:a","aac","-b:a","160k",
        "-t", f"{dur_video:.3f}",
        "-movflags","+faststart",
        salida,
    ], check=True)
    return salida


def aplica_narracion(video_path, texto):
    """Punto de entrada. Devuelve (ruta_video_final, n_caracteres).

    El texto puede venir en dos formatos:
      - "hook | cierre"  -> reparto temporal (hook al principio, cierre al final).
      - "texto corrido"  -> una sola pieza con respiro inicial (clasico).
    """
    bruto = (texto or "").strip()
    n_chars = len(bruto.replace(SEP, " "))
    partes = [p.strip() for p in bruto.split(SEP) if p.strip()]
    try:
        salida = video_path.replace(".mp4", "_voz.mp4")
        if salida == video_path:
            salida = video_path + "_voz.mp4"

        if len(partes) >= 2:
            hook_txt   = partes[0]
            cierre_txt = partes[-1]
            if len(partes) > 2:
                hook_txt = ". ".join(partes[:-1])
            t = int(time.time())
            hook_mp3   = os.path.join(tempfile.gettempdir(), f"iris_hook_{t}.mp3")
            cierre_mp3 = os.path.join(tempfile.gettempdir(), f"iris_cierre_{t}.mp3")
            _genera_voz(hook_txt,   hook_mp3)
            _genera_voz(cierre_txt, cierre_mp3)
            _mezcla_repartida(video_path, hook_mp3, cierre_mp3, salida)
            for f in (hook_mp3, cierre_mp3):
                try: os.remove(f)
                except OSError: pass
        else:
            tmp_mp3 = os.path.join(tempfile.gettempdir(), f"iris_voz_{int(time.time())}.mp3")
            _genera_voz(bruto, tmp_mp3)
            _mezcla_simple(video_path, tmp_mp3, salida)
            try: os.remove(tmp_mp3)
            except OSError: pass

        _log("narracion aplicada:", os.path.basename(salida),
             f"(video {_dur(video_path):.1f}s - {n_chars} caracteres - "
             f"{'reparto' if len(partes) >= 2 else 'simple'})")
        return salida, n_chars
    except urllib.error.HTTPError as e:
        cuerpo = ""
        try: cuerpo = e.read().decode("utf-8", "ignore")[:200]
        except Exception: pass
        _log("ElevenLabs HTTP", e.code, "-> reel sin voz.", cuerpo)
        return video_path, 0
    except Exception as e:
        _log("narracion no aplicada (reel sale mudo):", repr(e))
        return video_path, 0
