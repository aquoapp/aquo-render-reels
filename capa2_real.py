# -*- coding: utf-8 -*-
"""
AQUO · CAPA 2 con METRAJE REAL.
1) Recorta cualquier clip a vertical 9:16 (quita franjas negras, centra).
2) Compone encima: velo de legibilidad + texto editorial + cierre de marca.
"""
import os, shutil, subprocess, math
from PIL import Image, ImageDraw, ImageFilter
from aquo_reel import W,H,NAVY,AGUA,MARFIL,OLIVA,font,linea_mixta
from aquo_motor import _tokens3, frame_cierre, ease, RITMOS, FPS

def detecta_area_util(frame_path):
    im=Image.open(frame_path).convert("RGB"); w,h=im.size; px=im.load()
    def brillo_col(x): return sum(sum(px[x,y]) for y in range(0,h,40))
    left=0
    for x in range(w):
        if brillo_col(x)>200: left=x; break
    right=w-1
    for x in range(w-1,-1,-1):
        if brillo_col(x)>200: right=x; break
    return left,right,w,h

def _dim_clip(clip_in):
    """Ancho y alto reales del clip via ffprobe."""
    out=subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
                        "-show_entries","stream=width,height","-of","csv=p=0",clip_in],
                       capture_output=True,text=True,check=True).stdout.strip()
    w,h=out.split(",")[:2]
    return int(w),int(h)

def recorta_vertical(clip_in, clip_out):
    """Lleva CUALQUIER clip a 1080x1920 (9:16) sin romperse.
    - Calcula el recorte por la proporción REAL del clip (no por brillo).
    - Si el clip ya es 9:16 (o más estrecho), no recorta de más: escala directo.
    - El crop SIEMPRE queda dentro de las dimensiones reales (clamp), así que
      ffmpeg nunca recibe un tamaño imposible."""
    TARGET = 9/16  # ancho/alto objetivo
    w,h = _dim_clip(clip_in)
    ar = w/h
    if abs(ar - TARGET) < 0.02:
        # ya es 9:16 → solo escalar
        vf = f"scale={W}:{H}"
    elif ar > TARGET:
        # más ancho que 9:16 → recorto los lados, centrado
        crop_w = min(w, int(round(h*TARGET)))
        x0 = max(0, (w-crop_w)//2)
        vf = f"crop={crop_w}:{h}:{x0}:0,scale={W}:{H}"
    else:
        # más estrecho que 9:16 → recorto arriba/abajo, centrado
        crop_h = min(h, int(round(w/TARGET)))
        y0 = max(0, (h-crop_h)//2)
        vf = f"crop={w}:{crop_h}:0:{y0},scale={W}:{H}"
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",clip_in,
                    "-vf",vf,"-an","-c:v","libx264","-pix_fmt","yuv420p","-crf","18",clip_out],check=True)
    return clip_out

def _velo(familia):
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    if familia=="PROFUNDO":
        for y in range(H):
            a=int(165*(y/H)**1.25); d.line([(0,y),(W,y)],fill=(6,18,34,a))
    else:
        for y in range(H):
            a=int(140*(y/H)**1.25); d.line([(0,y),(W,y)],fill=(247,244,239,a))
    return ov

def texto_overlay(l1,l2,l3,familia,alpha=255):
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); draw=ImageDraw.Draw(ov)
    c_tenue=(228,231,235) if familia=="PROFUNDO" else (60,64,54)
    c_pleno=MARFIL if familia=="PROFUNDO" else NAVY
    f_reg=font("serif",92,400); f_bold=font("serif",150,700)
    bse=1240
    def col(c): return (c[0],c[1],c[2],alpha)
    linea_mixta(draw,bse-150,[(l1,f_reg,col(c_tenue))])
    linea_mixta(draw,bse+20,[(l2,f_bold,col(c_pleno))])
    l3t=[(t[0],t[1],col(t[2])) for t in _tokens3(l3,familia)]
    linea_mixta(draw,bse+185,l3t)
    return ov

def crea_reel_metraje(clip_in, guion, salida, familia="PROFUNDO", ritmo="sereno", cierre="auto"):
    """Reel de capa 2: clip real recortado + capa de marca encima."""
    vert="_vert.mp4"; recorta_vertical(clip_in, vert)
    # extraigo TODOS los frames del clip vertical
    tmp="_c2real"; shutil.rmtree(tmp,ignore_errors=True); os.makedirs(tmp)
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",vert,
                    "-vf",f"fps={FPS}",f"{tmp}/bg%04d.png"],check=True)
    bgs=sorted([f for f in os.listdir(tmp) if f.startswith("bg")])
    nbg=len(bgs)
    velo=_velo(familia)
    R=RITMOS[ritmo]; ff=R["fade"]/R["dur_esc"]; n=0
    out="_c2out"; shutil.rmtree(out,ignore_errors=True); os.makedirs(out)
    # una escena de texto por clip (el metraje manda el largo); loop del bg si hace falta
    nf_total=int(R["dur_esc"]*FPS)
    for e in guion:
        for i in range(nf_total):
            t=i/nf_total
            bg=Image.open(f"{tmp}/{bgs[n % nbg]}").convert("RGBA")
            bg.alpha_composite(velo)
            a=int(255*ease(max(0,min(1,min(t/ff,(1-t)/ff)))))
            bg.alpha_composite(texto_overlay(e["l1"],e["l2"],e["l3"],familia,a))
            bg.convert("RGB").save(f"{out}/f{n:04d}.png"); n+=1
    # cierre: último frame del clip congelado + marca
    last=Image.open(f"{tmp}/{bgs[min(n,nbg)-1]}").convert("RGBA")
    for i in range(int(R["cierre"]*FPS)):
        t=i/(R["cierre"]*FPS)
        bg=last.copy(); bg.alpha_composite(velo)
        bg=frame_cierre(bg.convert("RGB"),familia,min(1,t/0.4),cierre=cierre).convert("RGBA")
        bg.convert("RGB").save(f"{out}/f{n:04d}.png"); n+=1
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-framerate",str(FPS),
                    "-i",f"{out}/f%04d.png","-c:v","libx264","-pix_fmt","yuv420p","-crf","19",
                    "-movflags","+faststart",salida],check=True)
    shutil.rmtree(tmp,ignore_errors=True); shutil.rmtree(out,ignore_errors=True)
    os.remove(vert)
    print(f"✓ {salida}")
