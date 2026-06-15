# -*- coding: utf-8 -*-
"""
AQUO · CAPA 2 — Texto y marca sobre METRAJE REAL.
Coge un vídeo de fondo (tu clip de stock) y le compone encima
la MISMA capa editorial del motor: texto 3 líneas + cierre.

Uso real: pon_marca_sobre_video("tu_clip.mp4", guion, "salida.mp4")
Aquí, como demo, genero un fondo de agua por código para enseñar el concepto.
"""
import os, shutil, subprocess, math
from PIL import Image, ImageDraw, ImageFilter
from aquo_reel import W,H,NAVY,AGUA,MARFIL,OLIVA,font,dibuja_baseline,linea_mixta
from aquo_motor import _tokens3, frame_cierre, ease, RITMOS, FPS

def _velo(img, familia):
    """Velo oscuro/claro para que el texto se lea sobre cualquier metraje."""
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    if familia=="PROFUNDO":
        # gradiente oscuro abajo donde va el texto
        for y in range(H):
            a=int(150* (y/H)**1.3)
            d.line([(0,y),(W,y)],fill=(6,18,34,a))
    else:
        for y in range(H):
            a=int(120*(y/H)**1.3)
            d.line([(0,y),(W,y)],fill=(247,244,239,a))
    return ov

def texto_overlay(l1,l2,l3,familia,alpha=255):
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); draw=ImageDraw.Draw(ov)
    c_tenue=(225,228,232) if familia=="PROFUNDO" else (70,74,62)
    c_pleno=MARFIL if familia=="PROFUNDO" else NAVY
    f_reg=font("serif",92,400); f_bold=font("serif",150,700)
    bse=1180  # más abajo, sobre el velo
    def col(c): return (c[0],c[1],c[2],alpha)
    linea_mixta(draw,bse-150,[(l1,f_reg,col(c_tenue))])
    linea_mixta(draw,bse+20,[(l2,f_bold,col(c_pleno))])
    l3t=[(t[0],t[1],col(t[2])) for t in _tokens3(l3,familia)]
    linea_mixta(draw,bse+185,l3t)
    return ov

def _demo_fondo_agua(seed=0):
    """DEMO: agua navy en movimiento generada por código (sustituible por clip real)."""
    frames=[]
    base=Image.new("RGB",(W,H),(10,28,50))
    return base

def render_capa2_demo(guion, salida, familia="PROFUNDO", ritmo="sereno"):
    """Demo del concepto: fondo de agua animado + capa de marca."""
    R=RITMOS[ritmo]; tmp="_c2"; shutil.rmtree(tmp,ignore_errors=True); os.makedirs(tmp)
    n=0; ff=R["fade"]/R["dur_esc"]
    velo=_velo(Image.new("RGBA",(W,H)),familia)
    for e in guion:
        nf=int(R["dur_esc"]*FPS)
        for i in range(nf):
            t=i/nf; phase=n*0.10
            # fondo agua: ondas sinusoidales de color que se mueven
            bg=Image.new("RGB",(W,H))
            px=bg.load()
            for y in range(0,H,2):
                shimmer=int(18*math.sin(y*0.012+phase)+12*math.sin(y*0.03-phase*1.4))
                r=max(0,8+shimmer//3); g=max(0,24+shimmer//2); b=max(0,46+shimmer)
                for x in range(0,W,2):
                    xshim=int(6*math.sin(x*0.02+phase*0.7))
                    px[x,y]=(r,g,min(70,b+xshim))
                    if x+1<W: px[x+1,y]=(r,g,min(70,b+xshim))
                if y+1<H:
                    for x in range(0,W,2):
                        px[x,y+1]=px[x,y]
                        if x+1<W: px[x+1,y+1]=px[x,y]
            bg=bg.filter(ImageFilter.GaussianBlur(8)).convert("RGBA")
            bg.alpha_composite(velo)
            a=int(255*ease(max(0,min(1,min(t/ff,(1-t)/ff)))))
            bg.alpha_composite(texto_overlay(e["l1"],e["l2"],e["l3"],familia,a))
            bg.convert("RGB").save(f"{tmp}/f{n:04d}.png"); n+=1
    # cierre sobre agua
    for i in range(int(R["cierre"]*FPS)):
        t=i/(R["cierre"]*FPS); phase=n*0.10
        bg=Image.new("RGB",(W,H),(9,26,48)).filter(ImageFilter.GaussianBlur(2)).convert("RGBA")
        bg.alpha_composite(velo)
        bg=frame_cierre(bg.convert("RGB"),familia,min(1,t/0.4)).convert("RGBA")
        bg.convert("RGB").save(f"{tmp}/f{n:04d}.png"); n+=1
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-framerate",str(FPS),
                    "-i",f"{tmp}/f%04d.png","-c:v","libx264","-pix_fmt","yuv420p","-crf","19",
                    "-movflags","+faststart",salida],check=True)
    shutil.rmtree(tmp,ignore_errors=True)
    print(f"✓ {salida}")
