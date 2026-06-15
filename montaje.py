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

DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "1crIrrHpiZu3PgX8ovhIWAqKIcNC9Rtby")
WEBHOOK_ENTREGA = os.environ.get(
    "WEBHOOK_ENTREGA", "https://hook.eu1.make.com/iebp5goalo1a39bsz04ib6aump4kkjx8")

def _log(*a): print("[montaje]", *a, flush=True)


def monta_reel(orden, salida):
    cwd = os.getcwd()
    os.chdir(MOTOR_DIR)
    try:
        capa = int(orden.get("capa", 1))
        familia = orden.get("familia")
        ritmo = orden.get("ritmo") or "sereno"
        if capa == 2:
            from capa2_real import crea_reel_metraje
            c1 = os.path.join(MOTOR_DIR, "clips", orden["clip"])
            c2 = os.path.join(MOTOR_DIR, orden["clip"])
            clip_path = c1 if os.path.exists(c1) else c2
            guion = orden["guion"]
            if isinstance(guion, dict): guion = [guion]
            crea_reel_metraje(clip_path, guion, salida=salida,
                              familia=familia or "PROFUNDO", ritmo=ritmo)
        else:
            from aquo_motor import crea_reel
            crea_reel(orden["guion"], salida=salida,
                      familia=familia, ritmo=ritmo, seed=orden.get("seed"))
    finally:
        os.chdir(cwd)
    return salida


def _carga_credenciales_google():
    """Carga el JSON de la cuenta de servicio de forma robusta.
    Orden: (1) Secret File en /etc/secrets/, (2) variable GOOGLE_SA_JSON.
    Tolera espacios/comillas envolventes accidentales al pegar en Render."""
    import json as _json
    # 1) Secret File (la vía recomendada para JSON con private_key multilínea)
    for ruta in ("/etc/secrets/GOOGLE_SA_JSON", "/etc/secrets/google_sa.json",
                 "/etc/secrets/credenciales.json"):
        if os.path.exists(ruta):
            with open(ruta, "r") as fh:
                return _json.loads(fh.read())
    # 2) Variable de entorno
    raw = os.environ.get("GOOGLE_SA_JSON", "").strip()
    # quita comillas envolventes accidentales
    if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
        raw = raw[1:-1]
    return _json.loads(raw)


def sube_a_drive(path_mp4, nombre):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    info = _carga_credenciales_google()
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"])
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    meta = {"name": nombre, "parents": [DRIVE_FOLDER_ID]}
    media = MediaFileUpload(path_mp4, mimetype="video/mp4", resumable=False)
    f = service.files().create(body=meta, media_body=media, fields="id").execute()
    fid = f["id"]
    service.permissions().create(
        fileId=fid, body={"role": "reader", "type": "anyone"}).execute()
    return f"https://drive.google.com/uc?export=download&id={fid}"


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
    """Punto de entrada del proceso spawn: monta, sube a Drive, avisa a Make."""
    try:
        pieza = orden.get("pieza", f"reel_{int(time.time())}")
        caption = orden.get("caption", "")
        nombre = f"{pieza}.mp4"
        out = os.path.join(tempfile.gettempdir(), nombre)
        _log("montando", pieza, "capa", orden.get("capa", 1))
        monta_reel(orden, out)
        _log("montado", os.path.getsize(out), "bytes")
        _log("subiendo a Drive...")
        url = sube_a_drive(out, nombre)
        _log("en Drive:", url)
        avisa_make(url, pieza, caption)
        _log("avisado Make. OK", pieza)
        try: os.remove(out)
        except OSError: pass
    except Exception as e:
        _log("ERROR:", repr(e))
        traceback.print_exc()
