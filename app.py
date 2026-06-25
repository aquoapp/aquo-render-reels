# -*- coding: utf-8 -*-
"""
AQUO · SERVICIO DE RENDER DE REELS (nube)
Servidor que Make/Netlify llama por HTTP. Recibe la orden, responde 202 al
instante, y monta el reel en un PROCESO spawn aparte (montaje.trabajo). El
montaje va en proceso —no en hilo— porque ffmpeg (subprocess) se cuelga dentro
de un hilo del servidor HTTP en Render. El proceso spawn limpio lo evita.
Vive en Render (Docker con ffmpeg). Credenciales por variable de entorno.
"""
import os, json, multiprocessing as mp
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import montaje  # lógica de montaje (importable limpio por el proceso spawn)

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
        if self.path == "/reels" or self.path.startswith("/reels?"):
            return self._reels()
        return self._json(404, {"ok": False, "error": "not found"})

    def _reels(self):
        """Galería permanente: lista los reels guardados en Supabase Storage.
        Aunque Telegram falle o no publiques, todo reel montado queda aquí.
        Lee del bucket (carpeta redes/reels) con la service key del entorno."""
        try:
            reels = montaje.lista_reels()
            return self._json(200, {"ok": True, "total": len(reels), "reels": reels})
        except Exception as e:
            return self._json(500, {"ok": False, "error": str(e)})

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
        # Proceso spawn (no hilo): evita que ffmpeg se cuelgue. No daemon, así
        # Render no lo mata al cerrar el request; termina solo al acabar.
        ctx = mp.get_context("spawn")
        p = ctx.Process(target=montaje.trabajo, args=(orden,))
        p.start()
        _log("lanzado montaje (proc) para", orden.get("pieza", "reel"), "pid", p.pid)
        return self._json(202, {"ok": True, "estado": "montando",
                                "pieza": orden.get("pieza", "reel")})

    def log_message(self, *a): pass

if __name__ == "__main__":
    _log(f"arrancando en :{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
