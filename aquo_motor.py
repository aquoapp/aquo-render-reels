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
ACENTO={"PROFUNDO":(150,160,120), "MARFIL":(90,98,62)}

def _parse_linea3(texto):
    """
    La línea 3 lleva la palabra clave entre *asteriscos*: 'un poco *más.*'
    Devuelve tokens [(texto, italica?, ...)] para el render.
    """
    partes=[]
    buff=""; ital=False
    i=0
    while i < len(texto):
        if texto[i]=="*":
            if buff: partes.append((buff,ital)); buff=""
            ital=not ital
        else:
            buff+=texto[i]
        i+=1
    if buff: partes.append((buff,ital))
    return partes

def _tokens3(texto, familia):
    fr=font("serif",92,400); fi=font("serif-it",112,500)
    c_tenue=(195,202,210) if familia=="PROFUNDO" else (92,96,82)
    acc=ACENTO[familia]
    out=[]
    for txt,ital in _parse_linea3(texto):
        out.append((txt, fi if ital else fr, acc if ital else c_tenue))
    return out

def frame_escena(bg,l1,l2,l3txt,familia,pin,pout):
    img=bg.copy().convert("RGBA"); ov=Image.new("RGBA",(W,H),(0,0,0,0)); draw=ImageDraw.Draw(ov)
    c_tenue=(195,202,210) if familia=="PROFUNDO" else (92,96,82)
    c_pleno=MARFIL if familia=="PROFUNDO" else NAVY
    f_reg=font("serif",92,400); f_bold=font("serif",150,700)
    bse=960; a=int(255*ease(max(0,min(1,min(pin,pout)))))
    def col(c): return (c[0],c[1],c[2],a)
    dy=int(10*(1-ease(max(0,min(1,pin)))))
    linea_mixta(draw,bse-150+dy,[(l1,f_reg,col(c_tenue))])
    linea_mixta(draw,bse+20+dy,[(l2,f_bold,col(c_pleno))])
    l3=[(t[0],t[1],col(t[2])) for t in _tokens3(l3txt,familia)]
    linea_mixta(draw,bse+185+dy,l3)
    img.alpha_composite(ov); return img.convert("RGB")

def frame_cierre(bg,familia,prog):
    """Cierre de marca AQUO con TRANSICIÓN de familia.
    El fondo de la escena vira suavemente hacia el registro OPUESTO
    (PROFUNDO→MARFIL o MARFIL→PROFUNDO) como gesto de firma; sobre ese
    fondo ya virado se posa el wordmark AQUO + la línea de luz agua.
    Firma intacta (bg,familia,prog): ningún consumidor se rompe."""
    prog=max(0,min(1,prog))
    op = "MARFIL" if familia=="PROFUNDO" else "PROFUNDO"
    # 1) VIRAJE de fondo: escena -> fondo de la familia opuesta (primer 55% del cierre)
    bg_op=fondo(op, 7)  # fondo limpio del registro opuesto (sin olivo: cierre sobrio)
    vira=ease(min(1, prog/0.55))
    base=Image.blend(bg.convert("RGB"), bg_op, vira).convert("RGBA")
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); draw=ImageDraw.Draw(ov)
    # 2) WORDMARK: color correcto para el fondo FINAL (el opuesto)
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
def crea_reel(escenas, salida, familia=None, ritmo=None, seed=None, escala_olivo=0.54, verbose=True):
    """
    escenas: lista de dicts {l1, l2, l3}  (l3 con *palabra clave* entre asteriscos)
    familia: 'PROFUNDO' | 'MARFIL' | None (aleatorio)
    ritmo:   'calmado' | 'sereno' | 'vivo' | None (aleatorio)
    seed:    int | None (aleatorio → fondo distinto cada vez)
    """
    if seed is None: seed=random.randint(1,9999)
    if familia is None: familia=random.choice(["PROFUNDO","MARFIL"])
    if ritmo is None: ritmo=random.choice(list(RITMOS.keys()))
    R=RITMOS[ritmo]
    tmp="_frames_tool"; shutil.rmtree(tmp,ignore_errors=True); os.makedirs(tmp)
    bg=fondo(familia,seed); bg=pon_olivo(bg,familia,escala=escala_olivo)
    n=0; ff=R["fade"]/R["dur_esc"]
    for e in escenas:
        nf=int(R["dur_esc"]*FPS)
        for i in range(nf):
            t=i/nf; pin=min(1,t/ff); pout=min(1,(1-t)/ff)
            frame_escena(bg,e["l1"],e["l2"],e["l3"],familia,pin,pout).save(f"{tmp}/f{n:04d}.png"); n+=1
    for i in range(int(R["cierre"]*FPS)):
        t=i/(R["cierre"]*FPS); frame_cierre(bg,familia,min(1,t/0.4)).save(f"{tmp}/f{n:04d}.png"); n+=1
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-framerate",str(FPS),
                    "-i",f"{tmp}/f%04d.png","-c:v","libx264","-pix_fmt","yuv420p","-crf","18",
                    "-movflags","+faststart",salida],check=True)
    shutil.rmtree(tmp,ignore_errors=True)
    if verbose:
        d=float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
            "-of","default=noprint_wrappers=1:nokey=1",salida],capture_output=True,text=True).stdout.strip())
        print(f"✓ {salida}  ·  familia={familia} ritmo={ritmo} seed={seed}  ·  {d:.1f}s")
    return {"salida":salida,"familia":familia,"ritmo":ritmo,"seed":seed}
