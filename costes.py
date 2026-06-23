# -*- coding: utf-8 -*-
"""
AQUO · Medidor de costes por generación.

Acumulador simple: cada capa que gaste dinero (ElevenLabs, Grok, OpenAI…)
añade una línea con su coste. Al final, el motor pide el desglose + total y
lo adjunta al mensaje que llega a Telegram.

Principio: el medidor es AGNÓSTICO de proveedor. Hoy solo gasta ElevenLabs;
cuando se conecte Grok u otro, basta llamar a `apunta(...)` desde esa capa y
el coste aparece solo, sin tocar este archivo ni el mensaje de entrega.

Tarifas (variables de entorno → ajustables sin tocar código):
  · ELEVENLABS_USD_POR_1000  voz, $/1000 caracteres   (def 0.30, Creator)
  · GROK_USD_IMAGEN          imagen base Grok, $/img    (def 0.07)
  · GROK_USD_VIDEO_SEG       vídeo Grok, $/segundo       (def 0.05)
  · USD_EUR                  conversión USD→EUR          (def 0.92)
"""
import os

USD_EUR = float(os.environ.get("USD_EUR", "0.92"))

TARIFAS = {
    "elevenlabs_1000_chars": float(os.environ.get("ELEVENLABS_USD_POR_1000", "0.30")),
    "grok_imagen":           float(os.environ.get("GROK_USD_IMAGEN", "0.07")),
    "grok_video_seg":        float(os.environ.get("GROK_USD_VIDEO_SEG", "0.05")),
}


class Medidor:
    """Acumula las líneas de coste de UNA generación."""
    def __init__(self):
        self.lineas = []  # [(concepto, detalle, eur), ...]

    def apunta(self, concepto, eur, detalle=""):
        """Añade una línea de coste ya calculada en €."""
        self.lineas.append((concepto, detalle, round(float(eur), 4)))

    # ── Calculadoras por proveedor (devuelven € y apuntan la línea) ──
    def voz_elevenlabs(self, n_chars):
        usd = (n_chars / 1000.0) * TARIFAS["elevenlabs_1000_chars"]
        eur = round(usd * USD_EUR, 4)
        self.apunta("Narración IRIS (ElevenLabs)", eur, f"{n_chars} caracteres")
        return eur

    def grok_imagen(self, n=1):
        eur = round(n * TARIFAS["grok_imagen"] * USD_EUR, 4)
        self.apunta("Imagen base (Grok)", eur, f"{n} img")
        return eur

    def grok_video(self, segundos):
        eur = round(segundos * TARIFAS["grok_video_seg"] * USD_EUR, 4)
        self.apunta("Vídeo generado (Grok)", eur, f"{segundos:.0f}s")
        return eur

    # ── Salida ──
    def total_eur(self):
        return round(sum(l[2] for l in self.lineas), 4)

    def bloque_telegram(self):
        """Texto del desglose para añadir al caption de Telegram."""
        if not self.lineas:
            return "\n\n— — —\n💸 Coste de esta generación: 0 € (sin servicios de pago)"
        filas = "\n".join(
            f"· {c}{(' — ' + d) if d else ''}: {e:.4f} €"
            for c, d, e in self.lineas
        )
        return (f"\n\n— — —\n💸 Coste de esta generación:\n{filas}"
                f"\n• TOTAL ≈ {self.total_eur():.4f} €")

    # ── Persistencia: registra cada línea en Supabase (tabla aquo_api_uso) ──
    def registra_supabase(self, pieza, thumb_url=None):
        """Guarda una fila por proveedor en aquo_api_uso del proyecto de MARKETING.
        Degradación elegante: si algo falla, NO rompe el reel (solo deja log).
        El coste se guarda en USD (columna coste_usd) para ser consistente con
        las filas ya existentes; el dashboard hace la conversión a € al leer."""
        if not self.lineas:
            return
        import os, json, urllib.request
        # Proyecto de MARKETING (nunca la PWA). Ref partido para no chocar con la env var.
        ref = os.environ.get("SUPABASE_PROJECT_REF", "ksknebtl" + "opbbhnkrpsrd")
        url_base = os.environ.get("SUPABASE_URL", f"https://{ref}.supabase.co")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not key:
            print("[costes] sin SUPABASE_SERVICE_KEY: no se registra el gasto", flush=True)
            return
        endpoint = f"{url_base}/rest/v1/aquo_api_uso"
        for concepto, detalle, eur in self.lineas:
            usd = round(eur / USD_EUR, 5) if USD_EUR else eur
            api = ("elevenlabs" if "ElevenLabs" in concepto
                   else "grok" if "Grok" in concepto else "otro")
            fila = {
                "api": api,
                "modelo": concepto,
                "tipo": "reel_narracion" if api == "elevenlabs" else "reel_clip",
                "pieza": pieza,
                "unidades": _num(detalle),
                "coste_usd": usd,
                "meta": {"detalle": detalle, "eur": eur,
                         **({"thumb": thumb_url} if thumb_url else {})},
            }
            try:
                req = urllib.request.Request(
                    endpoint, data=json.dumps(fila).encode("utf-8"), method="POST",
                    headers={"apikey": key, "Authorization": f"Bearer {key}",
                             "Content-Type": "application/json", "Prefer": "return=minimal"})
                urllib.request.urlopen(req, timeout=20)
            except Exception as e:
                print("[costes] no se pudo registrar gasto:", repr(e), flush=True)


def _num(detalle):
    """Extrae el primer número de un detalle tipo '124 caracteres' → 124."""
    import re
    m = re.search(r"[\d.]+", detalle or "")
    try: return float(m.group()) if m else 0
    except Exception: return 0
