# -*- coding: utf-8 -*-
"""
AQUO · WORKER DE RENDER (proceso independiente)
Lo llama app.py vía subprocess. Recibe la orden como JSON por argumento,
monta el .mp4 con el motor, lo sube a Drive y avisa a Make.
Correr en proceso aparte es lo único fiable: ffmpeg vía subprocess se cuelga
dentro de hilos y de multiprocessing-fork del servidor HTTP.
"""
import os, sys, json, time, tempfile, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
MOTOR_DIR = os.path.join(HERE, "motor")
sys.path.insert(0, MOTOR_DIR)
os.chdir(MOTOR_DIR)


def _log(*a):
    print("[worker]", *a, flush=True)


def monta_reel(orden, salida):
    capa = int(orden.get("capa", 1))
    familia = orden.get("familia")
    ritmo = orden.get("ritmo") or "sereno"
    if capa == 2:
        from capa2_real import crea_reel_metraje
        clip_path = os.path.join(MOTOR_DIR, "clips", orden["clip"])
        guion = orden["guion"]
        if isinstance(guion, dict):
            guion = [guion]
        crea_reel_metraje(clip_path, guion, salida=salida,
                          familia=familia or "PROFUNDO", ritmo=ritmo)
    else:
        from aquo_motor import crea_reel
        crea_reel(orden["guion"], salida=salida,
                  familia=familia, ritmo=ritmo, seed=orden.get("seed"))
    return salida


def sube_a_drive(path_mp4, nombre):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    info = json.loads(os.environ.get("GOOGLE_SA_JSON", "{}"))
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"])
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    folder = os.environ.get("DRIVE_FOLDER_ID", "1crIrrHpiZu3PgX8ovhIWAqKIcNC9Rtby")
    meta = {"name": nombre, "parents": [folder]}
    media = MediaFileUpload(path_mp4, mimetype="video/mp4", resumable=False)
    f = service.files().create(body=meta, media_body=media, fields="id").execute()
    fid = f["id"]
    service.permissions().create(
        fileId=fid, body={"role": "reader", "type": "anyone"}).execute()
    return f"https://drive.google.com/uc?export=download&id={fid}"


def avisa_make(video_url, pieza, caption):
    import urllib.request
    webhook = os.environ.get(
        "WEBHOOK_ENTREGA",
        "https://hook.eu1.make.com/iebp5goalo1a39bsz04ib6aump4kkjx8")
    payload = json.dumps({
        "s1": video_url, "s2": video_url, "s3": video_url,
        "s4": video_url, "s5": video_url,
        "pieza": pieza, "caption": caption, "tipo": "reel",
    }).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def main():
    orden = json.loads(sys.argv[1])
    pieza = orden.get("pieza", f"reel_{int(time.time())}")
    caption = orden.get("caption", "")
    nombre = f"{pieza}.mp4"
    out = os.path.join(tempfile.gettempdir(), nombre)
    _log("montando", pieza, "capa", orden.get("capa", 1))
    monta_reel(orden, out)
    _log("montado", os.path.getsize(out), "bytes")
    if os.environ.get("AQUO_TEST_MODE") == "1":
        json.dump({"montado": True, "size": os.path.getsize(out), "pieza": pieza},
                  open(os.path.join(tempfile.gettempdir(), "render_result.json"), "w"))
        _log("TEST OK")
        return
    url = sube_a_drive(out, nombre)
    _log("en Drive:", url)
    avisa_make(url, pieza, caption)
    _log("avisado Make. OK", pieza)
    try:
        os.remove(out)
    except OSError:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _log("ERROR", str(e))
        traceback.print_exc()
        sys.exit(1)
