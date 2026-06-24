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

    def _descarga(clip_url):
        dest = os.path.join(tempfile.gettempdir(), f"clip_remoto_{int(time.time()*1000)}.mp4")
        _log("descargando clip remoto:", clip_url)
        req = urllib.request.Request(clip_url, headers={"User-Agent": "aquo-render/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as fh:
            fh.write(r.read())
        sz = os.path.getsize(dest)
        if sz < 1024:
            raise RuntimeError(f"el clip remoto pesa {sz} bytes; ¿URL caducada o privada?")
        _log("clip remoto descargado:", sz, "bytes")
        return dest

    # Varios clips remotos (capa 3 multi-clip de Grok)
    clips_remotos = orden.get("clips_remotos")
    if clips_remotos:
        return [_descarga(u) for u in clips_remotos]

    clip_url = orden.get("clipUrl") or orden.get("clip_url")
    if clip_url:
        return _descarga(clip_url)

    # ── 4º camino: BANCO INTELIGENTE (auto por pilar/familia) ──
    # Si el panel no mandó clip pero sí pilar o familia, el banco elige una
    # secuencia coherente (apertura→cuerpo→cierre) entre los clips que existen
    # en el repo. Devuelve una LISTA de rutas locales (capa2 ya admite lista).
    try:
        from banco_clips import selecciona_secuencia, clips_disponibles, resuelve
        if clips_disponibles():
            n_esc = len(orden.get("guion") or []) or 4
            nombres = selecciona_secuencia(
                pilar=orden.get("pilar"),
                familia=orden.get("familia"),
                n_escenas=n_esc,
                seed=orden.get("seed"),
            )
            # Cada nombre se resuelve a ruta local (dev) o URL Supabase (prod).
            origenes = [resuelve(n) for n in nombres]
            _log("banco inteligente eligió:", nombres)
            rutas = []
            for o in origenes:
                if o.startswith("http"):
                    rutas.append(_descarga(o))   # descarga de Supabase a /tmp
                else:
                    rutas.append(o)              # ya es local
            return rutas
    except Exception as e:
        _log("banco inteligente no disponible, sigo al error:", repr(e))

    raise RuntimeError(
        "capa 2 sin clip: falta 'clip' (banco local), 'clipUrl'/'clips_remotos' "
        "(vídeo remoto) o 'pilar'/'familia' (banco inteligente)")


def monta_reel(orden, salida):
    cwd = os.getcwd()
    os.chdir(MOTOR_DIR)
    try:
        capa_raw = orden.get("capa", 1)
        es_pluma = (str(capa_raw).lower() == "pluma")
        capa = 1 if es_pluma else int(capa_raw)
        familia = orden.get("familia")
        ritmo = orden.get("ritmo") or "sereno"
        cierre = orden.get("cierre") or "auto"   # 'MARFIL'|'PROFUNDO'|'auto' (Ana elige el registro del cierre)
        escala_texto = float(orden.get("escala_texto") or 1.0)   # tamaño de letra elegible (S/M/L)
        if es_pluma:
            # ── PLUMA: caligrafía manuscrita (Allura) sobre papel real. ──
            # Formato editorial íntimo (ACOMPAÑAMIENTO/DENTRO). Rescatado del
            # motor original; estaba construido y validado pero desconectado.
            from anim_pluma import render_pluma
            g = orden["guion"]
            if isinstance(g, dict): g = [g]
            # Las frases manuscritas salen de l1/l2 de cada escena; el subtexto
            # (firma en Cormorant) del último l3 limpio, o del campo 'subtexto'.
            lineas = []
            for e in g:
                for k in ("l1", "l2"):
                    v = (e.get(k) or "").strip()
                    if v: lineas.append(v)
            subtexto = (orden.get("subtexto")
                        or (g[-1].get("l3","").replace("*","").strip() if g else ""))
            render_pluma(lineas, subtexto, salida=salida,
                         papel=orden.get("papel") or "papel_pluma.png",
                         ritmo=ritmo if ritmo in ("calmado","sereno","vivo") else "calmado")
        elif capa == 2:
            from capa2_real import crea_reel_metraje
            clip_path = _resuelve_clip(orden)   # str (1 clip) o list (varios)
            guion = orden["guion"]
            if isinstance(guion, dict): guion = [guion]
            crea_reel_metraje(clip_path, guion, salida=salida,
                              familia=familia or "PROFUNDO", ritmo=ritmo, cierre=cierre)
            # Limpieza: borra cualquier clip que sea temporal (descargado de
            # Supabase/Grok a la carpeta temporal). Los clips locales del repo
            # NO se borran. Robusto para banco remoto, clipUrl y clips_remotos.
            import tempfile
            tmpdir = tempfile.gettempdir()
            for p in (clip_path if isinstance(clip_path, list) else [clip_path]):
                try:
                    if isinstance(p, str) and p.startswith(tmpdir):
                        os.remove(p)
                except OSError:
                    pass
        else:
            from aquo_motor import crea_reel
            crea_reel(orden["guion"], salida=salida,
                      familia=familia, ritmo=ritmo, seed=orden.get("seed"), cierre=cierre, escala_texto=escala_texto)
    finally:
        os.chdir(cwd)
    return salida


# ── Subida a Supabase Storage (misma vía que las imágenes de entrega.mjs) ──
# El ref se parte para que no coincida literal con la variable de entorno.
PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF", "ksknebtl" + "opbbhnkrpsrd")  # MOTOR REDES (marketing); NUNCA la PWA
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
        # ── Capa 3: clip(s) a medida con Grok ANTES de montar. Si falla, cae al banco. ──
        if int(orden.get("capa", 1)) == 3:
            try:
                from grok_clip import genera_clips
                _log("capa 3: generando clips con Grok...")
                urls = genera_clips(orden, medidor=medidor)
                if not urls:
                    raise RuntimeError("Grok no devolvió ningún clip")
                orden["clips_remotos"] = urls   # lista → capa 2 reparte escenas
                orden["capa"] = 2
                _log(f"capa 3: {len(urls)} clip(s) Grok listo(s), montando como capa 2")
            except Exception as e:
                _log("capa 3 falló, caigo al banco:", repr(e))
                orden["capa"] = 2
                orden.pop("clips_remotos", None)
                orden.pop("clipUrl", None)
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
