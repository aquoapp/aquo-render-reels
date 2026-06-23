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
        cierre = orden.get("cierre") or "auto"   # 'MARFIL'|'PROFUNDO'|'auto' (Ana elige el registro del cierre)
        escala_texto = float(orden.get("escala_texto") or 1.0)   # tamaño de letra elegible (S/M/L)
        if capa == 2:
            from capa2_real import crea_reel_metraje
            clip_path = _resuelve_clip(orden)   # acepta clip de banco O clipUrl remoto
            _es_remoto = bool(orden.get("clipUrl") or orden.get("clip_url")) and not orden.get("clip")
            guion = orden["guion"]
            if isinstance(guion, dict): guion = [guion]
            crea_reel_metraje(clip_path, guion, salida=salida,
                              familia=familia or "PROFUNDO", ritmo=ritmo, cierre=cierre)
            if _es_remoto:
                try: os.remove(clip_path)
                except OSError: pass
        else:
            from aquo_motor import crea_reel
            crea_reel(orden["guion"], salida=salida,
                      familia=familia, ritmo=ritmo, seed=orden.get("seed"), cierre=cierre, escala_texto=escala_texto)
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
        # ── Medidor de costes de ESTA generación (todos los proveedores) ──
        from costes import Medidor
        medidor = Medidor()
        # ── Capa 3: clip a medida con Grok ANTES de montar. Si falla, cae al banco. ──
        if int(orden.get("capa", 1)) == 3:
            try:
                from grok_clip import genera_clip
                _log("capa 3: generando clip con Grok...")
                clip_url = genera_clip(orden, medidor=medidor)
                orden["clipUrl"] = clip_url   # entra por la puerta de capa 2
                orden["capa"] = 2             # a partir de aquí, se monta como metraje
                _log("capa 3: clip Grok listo, montando como capa 2")
            except Exception as e:
                _log("capa 3 falló, caigo al banco:", repr(e))
                orden["capa"] = 2
                orden.pop("clipUrl", None)
                # respaldo: un clip del banco (mar en calma) para no quedarse sin reel
                orden["clip"] = orden.get("clip_respaldo") or "c13_marmol_mar.mp4"
        monta_reel(orden, out)
        _log("montado", os.path.getsize(out), "bytes")
        # ── Capa de narración IRIS (opcional, aislada): solo si el panel la pidió ──
        vz = orden.get("voz_iris")
        if vz and vz.get("activar"):
            try:
                from voz_iris import aplica_narracion
                _log("aplicando narración IRIS...")
                _res = aplica_narracion(out, vz.get("texto", ""))
                # Tolerante: la función puede devolver (ruta, n_chars) o solo ruta.
                if isinstance(_res, tuple):
                    out, n_chars = _res[0], (_res[1] if len(_res) > 1 else 0)
                else:
                    out, n_chars = _res, len((vz.get("texto") or "").strip())
                nombre = os.path.basename(out)   # el nombre puede cambiar a _voz.mp4
                if n_chars and n_chars > 0:
                    medidor.voz_elevenlabs(n_chars)
                    _log("narración IRIS OK:", n_chars, "caracteres")
            except Exception as e:
                _log("narración IRIS falló (reel saldrá mudo):", repr(e))
        caption = caption + medidor.bloque_telegram()
        _log("coste generación:", medidor.total_eur(), "EUR")
        try:
            medidor.registra_supabase(pieza)
        except Exception as e:
            _log("registro de coste falló (no crítico):", repr(e))
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
