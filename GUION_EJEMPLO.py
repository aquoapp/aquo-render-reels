# ════════════════════════════════════════════════════════════
#   AQUO · GUION DE REEL
#   Lo único que rellenas tú. Cero código que entender.
# ════════════════════════════════════════════════════════════
#
#   CÓMO FUNCIONA CADA ESCENA (3 líneas):
#     l1 = línea pequeña de arriba (tenue)
#     l2 = línea grande del medio (la frase fuerte)
#     l3 = línea de abajo. La PALABRA CLAVE va entre *asteriscos*
#          → esa palabra sale en itálica y color oliva
#
#   Ejemplo:  'y más *calma.*'  →  "y más" normal + "calma." resaltada
#
# ════════════════════════════════════════════════════════════

from aquo_motor import crea_reel

# ── TU GUION (cambia solo los textos) ───────────────────────
guion = [
    {"l1": "Hay",              "l2": "señales",        "l3": "que no hacen *ruido.*"},
    {"l1": "Tu cuerpo no",     "l2": "te lo grita.",   "l3": "Te lo *susurra.*"},
    {"l1": "AQUO ordena",      "l2": "lo que sientes", "l3": "para que tenga *sentido.*"},
]

# ── AJUSTES (opcionales — si los dejas en None, el motor decide y varía solo) ──
crea_reel(
    guion,
    salida   = "MI_REEL.mp4",
    familia  = None,    # "PROFUNDO" (navy) · "MARFIL" (claro) · None = aleatorio
    ritmo    = None,    # "calmado" · "sereno" · "vivo" · None = aleatorio
    seed     = None,    # None = fondo distinto cada vez
)
