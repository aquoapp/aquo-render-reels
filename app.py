# -*- coding: utf-8 -*-
"""
AQUO · SERVICIO DE RENDER DE REELS (nube)
Servidor pequeño que Make llama por HTTP. Recibe la orden, responde 202 rápido,
y lanza render_worker.py como proceso independiente para montar el .mp4, subirlo
a Drive y avisar a Make. El worker corre aparte porque ffmpeg vía subprocess se
cuelga dentro de hilos del servidor HTTP.
NO corre en Netlify (necesita ffmpeg). Vive en Render (Docker con ffmpeg).
Credenciales SIEMPRE por variable de entorno, nunca en el código.
"""
import os, sys, json, subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(HERE, "render_worker.py")
RENDER_TOKEN = os.environ.get("RENDER_TOKEN", "")
PORT = int(os.environ.get("PORT", "10000"))

def _log(*a): print("[server]", *a, flush=True)

class Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/health"):
            return self._json(200, {"ok": True, "service": "aquo-render-reels"})
        return self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if self.path != "/render":
            return self._json(404, {"ok": False, "error": "usa POST /render"})
        if RENDER_TOKEN and self.headers.get("X-AQUO-TOKEN") != RENDER_TOKEN:
            return self._json(401, {"ok": False, "error": "token invalido"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            orden = json.loads(self.rfile.read(n) or "{}")
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"json invalido: {e}"})
        if not orden.get("guion"):
            return self._json(400, {"ok": False, "error": "falta 'guion'"})
        subprocess.Popen([sys.executable, WORKER, json.dumps(orden)],
                         env=os.environ.copy(),
                         start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _log("lanzado worker para", orden.get("pieza", "reel"))
        return self._json(202, {"ok": True, "estado": "montando",
                                "pieza": orden.get("pieza", "reel")})

    def log_message(self, *a): pass

if __name__ == "__main__":
    _log(f"arrancando en :{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
