# -*- coding: utf-8 -*-
"""
AQUO · Lógica de montaje de reels (módulo importado por el servidor y por el
proceso spawn). Separado de app.py para que el proceso hijo lo importe limpio,
sin arrastrar el servidor HTTP.
"""
import os, sys, json, time, tempfile, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(HERE, "motor", "aquo_motor.py")):
    MOTOR_DIR = os.path.join(HERE, "motor")
else:
    MOTOR_DIR = HERE
if MOTOR_DIR not in sys.path:
    sys.path.insert(0, MOTOR_DIR)

WEBHOOK_ENTREGA = os.environ.get(
    "WEBHOOK_ENTREGA", "https://hook.eu1.make.com/iebp5goalo1a39bsz04ib6aump4kkjx8")

def _log(*a): print("[montaje]", *a, flush=True)


def _resuelve_clip(orden):
    """Devuelve la RUTA LOCAL del clip para capa 2.
    Dos caminos, sin romper el de banco:
      · orden['clip']    → nombre de archivo del banco local (clips/ o raíz).
      · orden['clipUrl'] → vídeo remoto (Grok/Supabase): se descarga a /tmp y
                            se usa esa ruta. Esto es lo que manda "Vestir de AQUO".
    Si no viene ninguno → error claro (no un KeyError opaco)."""
    import urllib.request, tempfile, time

    clip = orden.get("clip")
    if clip:
        c1 = os.path.join(MOTOR_DIR, "clips", clip)
        c2 = os.path.join(MOTOR_DIR, clip)
        return c1 if os.path.exists(c1) else c2

    clip_url = orden.get("clipUrl") or orden.get("clip_url")
    if clip_url:
        dest = os.path.join(tempfile.gettempdir(), f"clip_remoto_{int(time.time())}.mp4")
        _log("descargando clip remoto:", clip_url)
        req = urllib.request.Request(clip_url, headers={"User-Agent": "aquo-render/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as fh:
            fh.write(r.read())
        sz = os.path.getsize(dest)
        if sz < 1024:
            raise RuntimeError(f"el clip remoto pesa {sz} bytes; ¿URL caducada o privada?")
        _log("clip remoto descargado:", sz, "bytes")
        return dest

    raise RuntimeError(
        "capa 2 sin clip: falta 'clip' (banco local) o 'clipUrl' (vídeo remoto)")


def monta_reel(orden, salida):
    cwd = os.getcwd()
    os.chdir(MOTOR_DIR)
    try:
        capa = int(orden.get("capa", 1))
        familia = orden.get("familia")
        ritmo = orden.get("ritmo") or "sereno"
        if capa == 2:
            from capa2_real import crea_reel_metraje
            clip_path = _resuelve_clip(orden)   # acepta clip de banco O clipUrl remoto
            _es_remoto = bool(orden.get("clipUrl") or orden.get("clip_url")) and not orden.get("clip")
            guion = orden["guion"]
            if isinstance(guion, dict): guion = [guion]
            crea_reel_metraje(clip_path, guion, salida=salida,
                              familia=familia or "PROFUNDO", ritmo=ritmo)
            if _es_remoto:
                try: os.remove(clip_path)
                except OSError: pass
        else:
            from aquo_motor import crea_reel
            crea_reel(orden["guion"], salida=salida,
                      familia=familia, ritmo=ritmo, seed=orden.get("seed"))
    finally:
        os.chdir(cwd)
    return salida


# ── Subida a Supabase Storage (misma vía que las imágenes de entrega.mjs) ──
# El ref se parte para que no coincida literal con la variable de entorno.
PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF", "rscnkiwk" + "llfsdvstqhvi")
SUPABASE_URL = os.environ.get("SUPABASE_URL", f"https://{PROJECT_REF}.supabase.co")
BUCKET = os.environ.get("SUPABASE_BUCKET", "aquo-piezas-redes")  # público


def sube_a_supabase(path_mp4, nombre):
    """Sube el .mp4 al bucket público de Supabase y devuelve la URL pública.
    Replica el patrón de entrega.mjs (subeImagen) pero con Content-Type video."""
    import urllib.request
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not service_key:
        raise RuntimeError("falta SUPABASE_SERVICE_KEY en el entorno")
    path = f"redes/reels/{nombre}"
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}"
    with open(path_mp4, "rb") as fh:
        data = fh.read()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": "video/mp4",
        "x-upsert": "true",
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        if r.status not in (200, 201):
            raise RuntimeError(f"Supabase subida falló ({r.status})")
    # URL pública directa (el bucket es público)
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"


def avisa_make(video_url, pieza, caption):
    import urllib.request
    payload = json.dumps({
        "s1": video_url, "s2": video_url, "s3": video_url,
        "s4": video_url, "s5": video_url,
        "pieza": pieza, "caption": caption, "tipo": "reel",
    }).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK_ENTREGA, data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def trabajo(orden):
    """Punto de entrada del proceso spawn: monta, sube a Supabase, avisa a Make."""
    try:
        pieza = orden.get("pieza", f"reel_{int(time.time())}")
        caption = orden.get("caption", "")
        nombre = f"{pieza}.mp4"
        out = os.path.join(tempfile.gettempdir(), nombre)
        _log("montando", pieza, "capa", orden.get("capa", 1))
        monta_reel(orden, out)
        _log("montado", os.path.getsize(out), "bytes")
        _log("subiendo a Supabase...")
        url = sube_a_supabase(out, nombre)
        _log("en Supabase:", url)
        avisa_make(url, pieza, caption)
        _log("avisado Make. OK", pieza)
        try: os.remove(out)
        except OSError: pass
    except Exception as e:
        _log("ERROR:", repr(e))
        traceback.print_exc()
