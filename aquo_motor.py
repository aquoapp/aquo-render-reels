# -*- coding: utf-8 -*-
"""
AQUO · MOTOR DE REELS — herramienta de uso simple.

USO (lo único que tú haces): rellenar un "guion" y ejecutar.
El motor decide ritmo, fondo y familia si no se especifican,
para que salga variedad sin que tengas que pensar nada.
"""
import os, shutil, random, subprocess, json
from PIL import Image, ImageDraw, ImageFilter
from aquo_reel import (W,H,NAVY,AGUA,MARFIL,OLIVA, font, fondo, pon_olivo,
                       dibuja_baseline, linea_mixta, _olivo_recortado)

FPS=30
def ease(t): return t*t*(3-2*t)

RITMOS={
  "calmado": {"dur_esc":4.2,"fade":0.8, "cierre":3.0},
  "sereno":  {"dur_esc":3.4,"fade":0.6, "cierre":2.6},
  "vivo":    {"dur_esc":2.4,"fade":0.42,"cierre":2.0},
}
# Acento de la palabra clave por familia
ACENTO={"PROFUNDO":(150,160,120), "MARFIL":(74,90,40)}

import re as _re
_PREFIJO_FORMATO = _re.compile(r'^\s*(REEL|POST|CARRUSEL|STORY|V[IÍ]DEO)\s*[·:\-]\s*', _re.IGNORECASE)
def _limpia_kicker(l1):
    """Quita el prefijo de formato del kicker si el guion lo trae (REEL · / POST · …)."""
    if not l1: return l1
    return _PREFIJO_FORMATO.sub('', l1).strip()


def _parse_linea3(texto):
    """
    La línea 3 lleva la palabra clave entre *asteriscos*: 'un poco *más.*'
    Devuelve tokens [(texto, italica?)] para el render.
    Robusto (fix 4): tolera asteriscos desbalanceados ('*escucharlo.' sin cierre)
    sin imprimir nunca el '*' crudo; un asterisco abierto se cierra implícitamente
    al final de la línea.
    """
    partes=[]
    buff=""; ital=False
    for ch in (texto or ""):
        if ch=="*":
            if buff: partes.append((buff,ital)); buff=""
            ital=not ital  # alterna; si queda abierto, lo cerramos abajo
        else:
            buff+=ch
    if buff: partes.append((buff,ital))
    return partes

def _tokens3(texto, familia, escala_texto=1.0):
    et=max(0.7, min(1.4, escala_texto or 1.0))
    fr=font("serif",int(92*et),400); fi=font("serif-it",int(112*et),500)
    c_tenue=(195,202,210) if familia=="PROFUNDO" else (74,80,70)
    acc=ACENTO[familia]
    out=[]
    for txt,ital in _parse_linea3(texto):
        out.append((txt, fi if ital else fr, acc if ital else c_tenue))
    return out

# Margen útil para el TEXTO. Más conservador que el de aquo_reel (96) porque el
# olivo de las plantillas ocupa la esquina superior; con 120px el texto no lo besa.
MARGEN_TEXTO = 150

def _factor_comun(draw, lineas, gap=14):
    """Mira las 3 líneas YA construidas (cada una lista de tokens) y devuelve un
    ÚNICO factor de encogido para todas. Así, si una línea se pasa, las tres
    bajan de tamaño a la vez y la JERARQUÍA visual se mantiene (la bold sigue
    siendo más grande que la regular). Devuelve 1.0 si todo ya cabía."""
    util = W - 2*MARGEN_TEXTO
    peor = 1.0
    for tokens in lineas:
        if not tokens: continue
        total = sum(draw.textlength(t[0], font=t[1]) for t in tokens) + (len(tokens)-1)*gap
        if total > util and total > 0:
            peor = min(peor, util/total)
    return peor

def _encoge(tokens, factor):
    if factor >= 0.999 or not tokens: return tokens
    return [(t[0], t[1].font_variant(size=max(1,int(t[1].size*factor))), t[2]) for t in tokens]

def frame_escena(bg,l1,l2,l3txt,familia,pin,pout,escala_texto=1.0):
    img=bg.copy().convert("RGBA"); ov=Image.new("RGBA",(W,H),(0,0,0,0)); draw=ImageDraw.Draw(ov)
    c_tenue=(195,202,210) if familia=="PROFUNDO" else (74,80,70)
    c_pleno=MARFIL if familia=="PROFUNDO" else NAVY
    # escala_texto: 1.0 = tamaño base. <1 más pequeño, >1 más grande (elegible por Ana).
    et=max(0.7, min(1.4, escala_texto or 1.0))
    f_reg=font("serif",int(92*et),400); f_bold=font("serif",int(150*et),700)
    bse=960; a=int(255*ease(max(0,min(1,min(pin,pout)))))
    def col(c): return (c[0],c[1],c[2],a)
    dy=int(10*(1-ease(max(0,min(1,pin)))))
    # 1) Construyo las 3 líneas como tokens, ANTES de dibujar.
    t1=[(_limpia_kicker(l1), f_reg, col(c_tenue))]
    t2=[(l2, f_bold, col(c_pleno))]
    t3=[(tk[0], tk[1], col(tk[2])) for tk in _tokens3(l3txt,familia,escala_texto=et)]
    # 2) Un único factor para las tres → jerarquía intacta, nada se sale.
    factor=_factor_comun(draw,[t1,t2,t3])
    # 3) Dibujo encogiendo solidariamente. max_w blinda por si una línea concreta
    #    aún se pasara (defensa en profundidad sobre el autoshrink de linea_mixta).
    util=W-2*MARGEN_TEXTO
    linea_mixta(draw,bse-150+dy,_encoge(t1,factor),max_w=util)
    linea_mixta(draw,bse+20+dy, _encoge(t2,factor),max_w=util)
    linea_mixta(draw,bse+185+dy,_encoge(t3,factor),max_w=util)
    img.alpha_composite(ov); return img.convert("RGB")

def frame_cierre(bg,familia,prog,cierre="auto"):
    """Cierre de marca AQUO con TRANSICIÓN de familia.
    cierre: 'MARFIL' | 'PROFUNDO' | 'auto'.
      · 'auto' (por defecto): vira al registro OPUESTO a la escena (gesto de firma clásico).
      · 'MARFIL'/'PROFUNDO': Ana elige el registro final del cierre, sin importar la familia
        de las escenas. Si coincide con la familia, no hay viraje (cierre del mismo tono).
    Firma retrocompatible: quien no pase 'cierre' obtiene el comportamiento de siempre."""
    prog=max(0,min(1,prog))
    if cierre in ("MARFIL","PROFUNDO"):
        op = cierre
    else:
        op = "MARFIL" if familia=="PROFUNDO" else "PROFUNDO"
    # 1) VIRAJE de fondo: escena -> fondo del registro de cierre (primer 55% del cierre)
    bg_op=fondo(op, 7)  # fondo limpio del registro de cierre (sin olivo: cierre sobrio)
    vira=ease(min(1, prog/0.55))
    base=Image.blend(bg.convert("RGB"), bg_op, vira).convert("RGBA")
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); draw=ImageDraw.Draw(ov)
    # 2) WORDMARK: color correcto para el fondo FINAL (el registro de cierre)
    c = MARFIL if op=="PROFUNDO" else NAVY
    aw=int(255*ease(max(0, min(1, (prog-0.35)/0.45))))  # entra tras iniciar el viraje
    f=font("display",130,800); w=draw.textlength("AQUO",font=f); asc,_=f.getmetrics()
    draw.text((W/2-w/2,H/2-asc/2-40),"AQUO",font=f,fill=(c[0],c[1],c[2],aw))
    # 3) LÍNEA DE LUZ AGUA bajo el wordmark, se abre desde el centro
    ly=int(H*0.60); grad=Image.new("RGBA",(W,8),(0,0,0,0)); gp=grad.load()
    spread=ease(max(0,min(1,(prog-0.35)/0.45)))
    for x in range(W):
        d=abs(x-W/2)/(W/2); vis=1 if d<spread else 0; al=int(200*(1-d)**2)*vis
        for yy in range(8): gp[x,yy]=(AGUA[0],AGUA[1],AGUA[2],al if yy in(3,4) else al//3)
    ov.alpha_composite(grad,(0,ly)); base.alpha_composite(ov); return base.convert("RGB")

# ── FUNCIÓN PRINCIPAL: crea_reel ─────────────────────────────
def crea_reel(escenas, salida, familia=None, ritmo=None, seed=None, escala_olivo=None, cierre="auto", escala_texto=1.0, verbose=True):
    """
    escenas: lista de dicts {l1, l2, l3}  (l3 con *palabra clave* entre asteriscos)
    familia: 'PROFUNDO' | 'MARFIL' | None (aleatorio)
    ritmo:   'calmado' | 'sereno' | 'vivo' | None (aleatorio)
    seed:    int | None (aleatorio → fondo distinto cada vez)
    cierre:  'MARFIL'|'PROFUNDO'|'auto' — registro del cierre de marca (auto=opuesto a la escena)
    """
    if seed is None: seed=random.randint(1,9999)
    if familia is None: familia=random.choice(["PROFUNDO","MARFIL"])
    if ritmo is None: ritmo=random.choice(list(RITMOS.keys()))
    R=RITMOS[ritmo]
    if escala_olivo is None:
        # MARFIL: olivo más recogido para que no caiga sobre el texto. PROFUNDO aguanta más.
        escala_olivo = 0.46 if familia=="MARFIL" else 0.54
    tmp="_frames_tool"; shutil.rmtree(tmp,ignore_errors=True); os.makedirs(tmp)
    bg=fondo(familia,seed); bg=pon_olivo(bg,familia,escala=escala_olivo)
    n=0; ff=R["fade"]/R["dur_esc"]
    for e in escenas:
        nf=int(R["dur_esc"]*FPS)
        for i in range(nf):
            t=i/nf; pin=min(1,t/ff); pout=min(1,(1-t)/ff)
            frame_escena(bg,e["l1"],e["l2"],e["l3"],familia,pin,pout,escala_texto=escala_texto).save(f"{tmp}/f{n:04d}.png"); n+=1
    for i in range(int(R["cierre"]*FPS)):
        t=i/(R["cierre"]*FPS); frame_cierre(bg,familia,min(1,t/0.4),cierre=cierre).save(f"{tmp}/f{n:04d}.png"); n+=1
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-framerate",str(FPS),
                    "-i",f"{tmp}/f%04d.png","-c:v","libx264","-pix_fmt","yuv420p","-crf","18",
                    "-movflags","+faststart",salida],check=True)
    shutil.rmtree(tmp,ignore_errors=True)
    if verbose:
        d=float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
            "-of","default=noprint_wrappers=1:nokey=1",salida],capture_output=True,text=True).stdout.strip())
        print(f"✓ {salida}  ·  familia={familia} ritmo={ritmo} seed={seed}  ·  {d:.1f}s")
    return {"salida":salida,"familia":familia,"ritmo":ritmo,"seed":seed}
