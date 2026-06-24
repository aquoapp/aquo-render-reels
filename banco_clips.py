# -*- coding: utf-8 -*-
"""
AQUO · BANCO DE CLIPS INTELIGENTE (capa 2)  ·  17 clips reales clasificados
===========================================================================
Mapa estratégico clip → pilar / familia / rol narrativo. Le da al motor el
criterio que le faltaba: saber QUÉ metraje va con QUÉ mensaje, sin que el panel
tenga que elegir clips a mano.

PRINCIPIO "no humo": `clips_disponibles()` filtra por presencia REAL en disco.
Si un clip del mapa no está físicamente, no se ofrece (nunca rompe el render).

Roles narrativos (para ordenar una secuencia coherente):
  apertura  → plano con movimiento/gancho (ideal para frío)
  cuerpo    → planos intermedios (intimidad, gesto, detalle)
  cierre    → plano de respiro/horizonte antes del wordmark

Pilares (claves sin tildes): CLARIDAD · ACOMPANAMIENTO · VIDA_REAL · DENTRO
Familias: PROFUNDO · MARFIL · None(=sirve para ambas)
Calidad: alta=720x1280 · media=416x752 (se prioriza alta en aperturas)
"""
import os, random

HERE = os.path.dirname(os.path.abspath(__file__))

# ── Resolución de origen de los clips ────────────────────────────────────────
# Los clips fuente viven en Supabase Storage (bucket público), NO en GitHub
# (los binarios pesados no van al repo). En desarrollo, si el clip existe en
# disco, se usa local; en producción (Render, sin clips en el repo), el banco
# devuelve la URL pública de Supabase y el motor la descarga (clips_remotos).
SUPA_URL    = os.environ.get("SUPABASE_URL", "https://ksknebtl" + "opbbhnkrpsrd.supabase.co")
SUPA_BUCKET = os.environ.get("SUPABASE_BUCKET", "aquo-piezas-redes")
CLIPS_PREFIX = os.environ.get("CLIPS_PREFIX", "redes/clips_fuente")  # carpeta en el bucket

def url_publica(nombre):
    """URL pública del clip en Supabase Storage."""
    return f"{SUPA_URL}/storage/v1/object/public/{SUPA_BUCKET}/{CLIPS_PREFIX}/{nombre}"

def resuelve(nombre):
    """Ruta local si el clip está en disco (dev); si no, URL de Supabase (prod)."""
    local = os.path.join(HERE, nombre)
    return local if os.path.exists(local) else url_publica(nombre)

CLIPS = {
    # ── AGUA / CLARIDAD ──────────────────────────────────────────────
    "c01_vaso_agua.mp4":        {"pilares":["CLARIDAD"],                 "familia":None,       "rol":"cuerpo",   "peso":2, "q":"alta", "desc":"vaso de agua reposado — lo que se asienta"},
    "c02_agua_sirviendose.mp4": {"pilares":["CLARIDAD"],                 "familia":"PROFUNDO", "rol":"apertura", "peso":3, "q":"alta", "desc":"agua cayendo a vaso — movimiento, gancho en frío"},
    "c12a_mar_calma.mp4":       {"pilares":["CLARIDAD","VIDA_REAL"],     "familia":"PROFUNDO", "rol":"cierre",   "peso":2, "q":"media","desc":"superficie de mar en calma — agua, respiro"},
    "c12b_mar_calma.mp4":       {"pilares":["CLARIDAD","VIDA_REAL"],     "familia":"PROFUNDO", "rol":"cierre",   "peso":2, "q":"media","desc":"superficie de mar en calma (toma B)"},
    "c13_marmol_mar.mp4":       {"pilares":["CLARIDAD","VIDA_REAL"],     "familia":"PROFUNDO", "rol":"cierre",   "peso":3, "q":"media","desc":"mármol frente al mar — horizonte, cierre"},

    # ── OLIVO / TEXTURA / CLARIDAD-DENTRO ────────────────────────────
    "c03_sombras_olivo.mp4":    {"pilares":["CLARIDAD","DENTRO"],        "familia":"MARFIL",   "rol":"apertura", "peso":2, "q":"alta", "desc":"sombras de hojas de olivo moviéndose — textura serena"},

    # ── ACOMPAÑAMIENTO / RITUAL / HOGAR ──────────────────────────────
    "c04_manos_taza.mp4":       {"pilares":["ACOMPANAMIENTO","VIDA_REAL"],"familia":None,      "rol":"cuerpo",   "peso":2, "q":"alta", "desc":"manos sosteniendo taza — intimidad, gesto"},
    "c06_cortina_luz.mp4":      {"pilares":["ACOMPANAMIENTO","VIDA_REAL"],"familia":"MARFIL",  "rol":"apertura", "peso":2, "q":"alta", "desc":"cortina meciéndose con luz — calma de hogar"},
    "c08_skincare.mp4":         {"pilares":["ACOMPANAMIENTO"],           "familia":None,       "rol":"cuerpo",   "peso":2, "q":"media","desc":"vaso de agua y sérum — ritual de autocuidado"},

    # ── VIDA REAL / COTIDIANO / MEDITERRÁNEO ─────────────────────────
    "c07_desayuno.mp4":         {"pilares":["VIDA_REAL"],                "familia":"MARFIL",   "rol":"cuerpo",   "peso":2, "q":"alta", "desc":"desayuno sereno con fruta — cotidiano"},
    "c09_arena_playa.mp4":      {"pilares":["VIDA_REAL","CLARIDAD"],     "familia":None,       "rol":"cierre",   "peso":2, "q":"alta", "desc":"orilla, arena mojada — horizonte cotidiano"},
    "c14_paseo_olivos.mp4":     {"pilares":["VIDA_REAL"],                "familia":None,       "rol":"cierre",   "peso":2, "q":"media","desc":"paseo entre mar y olivos — mediterráneo"},
    "c15_chillout.mp4":         {"pilares":["VIDA_REAL","ACOMPANAMIENTO"],"familia":"MARFIL",  "rol":"cuerpo",   "peso":1, "q":"media","desc":"terraza chillout atardecer — descanso"},

    # ── DENTRO DE AQUO / TRABAJO / EL "RUIDO" DEL DÍA ────────────────
    "c05a_cuaderno.mp4":        {"pilares":["DENTRO"],                   "familia":None,       "rol":"cuerpo",   "peso":2, "q":"alta", "desc":"pasar páginas de cuaderno — reflexión, registro"},
    "c05b_cuaderno.mp4":        {"pilares":["DENTRO"],                   "familia":None,       "rol":"cuerpo",   "peso":1, "q":"alta", "desc":"pasar páginas de cuaderno (toma B)"},
    "c10_movil_mesa.mp4":       {"pilares":["DENTRO","CLARIDAD"],        "familia":None,       "rol":"apertura", "peso":2, "q":"media","desc":"móvil sobre mesa con vaso y olivo — el ruido disperso del día"},
    "c11_escritorio.mp4":       {"pilares":["DENTRO"],                   "familia":None,       "rol":"cuerpo",   "peso":2, "q":"media","desc":"escritorio sereno, café y libreta — trabajo en calma"},
}

def _existe_local(n): return os.path.exists(os.path.join(HERE, n))

def clips_disponibles():
    """Todos los clips del mapa están disponibles: en disco (dev) o en Supabase
    (prod). Se asume que el banco completo está subido al bucket. Si quieres
    forzar SOLO los presentes en disco, exporta CLIPS_SOLO_LOCAL=1."""
    if os.environ.get("CLIPS_SOLO_LOCAL") == "1":
        return {n: m for n, m in CLIPS.items() if _existe_local(n)}
    return dict(CLIPS)

def _norm(p):
    if not p: return None
    return (p.upper().replace("Ó","O").replace("Ñ","N").replace("Á","A")
             .replace("É","E").replace("Í","I").replace("Ú","U").replace(" ","_").strip())

def selecciona_secuencia(pilar=None, familia=None, n_escenas=4, seed=None):
    """Secuencia de clips (longitud n_escenas) ordenada apertura→cuerpo→cierre,
    filtrando por pilar/familia. Relaja filtros antes que devolver vacío.
    Prioriza calidad 'alta' en la apertura. Evita repetir si hay material."""
    rng = random.Random(seed)
    disp = clips_disponibles()
    P, F = _norm(pilar), (familia.upper().strip() if familia else None)

    def casa(m, up=True, uf=True):
        if uf and F and m["familia"] not in (None, F): return False
        if up and P and P not in [_norm(x) for x in m["pilares"]]: return False
        return True

    for up,uf in [(True,True),(False,True),(False,False)]:
        cand = {n:m for n,m in disp.items() if casa(m,up,uf)}
        if cand: break

    por_rol = {"apertura":[], "cuerpo":[], "cierre":[]}
    for n,m in cand.items(): por_rol.get(m["rol"],por_rol["cuerpo"]).append((n,m))
    # apertura: prioriza alta calidad
    por_rol["apertura"].sort(key=lambda x: (x[1]["q"]!="alta", rng.random()))
    for r in ("cuerpo","cierre"): rng.shuffle(por_rol[r])

    usados=set(); sec=[]
    def toma(lst):
        for n,_ in lst:
            if n not in usados: usados.add(n); return n
        return None

    a = toma(por_rol["apertura"]) or toma(por_rol["cuerpo"]) or toma(por_rol["cierre"])
    if a: sec.append(a)
    cierre = None
    if n_escenas>=2:
        cierre = toma(por_rol["cierre"]) or None
    pool = por_rol["cuerpo"]+por_rol["apertura"]+por_rol["cierre"]
    while len(sec) < (n_escenas-(1 if cierre else 0)):
        n = toma(pool)
        if not n:  # agotado: permitir repetición controlada
            todos=list(cand.keys()); n=rng.choice(todos) if todos else list(disp.keys())[0]
        sec.append(n)
    if cierre: sec.append(cierre)
    while len(sec) < n_escenas:
        todos=list(cand.keys()); sec.append(rng.choice(todos) if todos else list(disp.keys())[0])
    return sec[:n_escenas]

if __name__ == "__main__":
    d = clips_disponibles()
    print(f"Clips en disco: {len(d)}/17")
    for pil in ["CLARIDAD","ACOMPANAMIENTO","VIDA_REAL","DENTRO"]:
        print(f"  {pil:16s}->", selecciona_secuencia(pilar=pil, n_escenas=4, seed=3))
