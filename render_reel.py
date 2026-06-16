# -*- coding: utf-8 -*-
"""AQUO · Render de reel a MP4. Timing ALTERNANTE por ritmo."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, shutil, random
from aquo_reel import (W,H,NAVY,AGUA,ARENA,MARFIL,OLIVA,TIERRA,AMBAR,
                       font, fondo, pon_olivo, dibuja_baseline, linea_mixta)
FPS=30
def ease(t): return t*t*(3-2*t)

# RITMOS: cada uno define duración de escena, fade y pausa del cierre
RITMOS={
  "calmado":  {"dur_esc":4.2, "fade":0.8,  "cierre":3.0},  # lento, respirado
  "sereno":   {"dur_esc":3.4, "fade":0.6,  "cierre":2.6},  # medio
  "vivo":     {"dur_esc":2.4, "fade":0.42, "cierre":2.0},  # más ágil
}

def frame_escena(bg,l1,l2,l3,familia,pin,pout):
    img=bg.copy().convert("RGBA"); ov=Image.new("RGBA",(W,H),(0,0,0,0)); draw=ImageDraw.Draw(ov)
    c_tenue=(195,202,210) if familia=="PROFUNDO" else (128,128,116)
    c_pleno=MARFIL if familia=="PROFUNDO" else NAVY
    f_reg=font("serif",92,400); f_bold=font("serif",150,700)
    bse=960; a=int(255*ease(max(0,min(1,min(pin,pout)))))
    def col(c): return (c[0],c[1],c[2],a)
    dy=int(10*(1-ease(max(0,min(1,pin)))))
    linea_mixta(draw,bse-150+dy,[(l1,f_reg,col(c_tenue))])
    linea_mixta(draw,bse+20+dy,[(l2,f_bold,col(c_pleno))])
    linea_mixta(draw,bse+185+dy,[(t[0],t[1],col(t[2])) for t in l3])
    img.alpha_composite(ov); return img.convert("RGB")

def frame_cierre(bg,familia,prog):
    """Cierre de marca AQUO con TRANSICIÓN de familia (idéntico a aquo_motor)."""
    prog=max(0,min(1,prog))
    op = "MARFIL" if familia=="PROFUNDO" else "PROFUNDO"
    bg_op=fondo(op, 7)
    vira=ease(min(1, prog/0.55))
    base=Image.blend(bg.convert("RGB"), bg_op, vira).convert("RGBA")
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); draw=ImageDraw.Draw(ov)
    c = MARFIL if op=="PROFUNDO" else NAVY
    aw=int(255*ease(max(0, min(1, (prog-0.35)/0.45))))
    f=font("display",130,800); w=draw.textlength("AQUO",font=f); asc,_=f.getmetrics()
    draw.text((W/2-w/2,H/2-asc/2-40),"AQUO",font=f,fill=(c[0],c[1],c[2],aw))
    ly=int(H*0.60); grad=Image.new("RGBA",(W,8),(0,0,0,0)); gp=grad.load()
    spread=ease(max(0,min(1,(prog-0.35)/0.45)))
    for x in range(W):
        d=abs(x-W/2)/(W/2); vis=1 if d<spread else 0; al=int(200*(1-d)**2)*vis
        for yy in range(8): gp[x,yy]=(AGUA[0],AGUA[1],AGUA[2],al if yy in(3,4) else al//3)
    ov.alpha_composite(grad,(0,ly)); base.alpha_composite(ov); return base.convert("RGB")

def render(escenas, familia, seed, outname, ritmo="sereno", escala_olivo=0.66):
    R=RITMOS[ritmo]
    tmp="_frames"; shutil.rmtree(tmp,ignore_errors=True); os.makedirs(tmp)
    bg=fondo(familia,seed); bg=pon_olivo(bg,familia,escala=escala_olivo)
    n=0; fade_frac=R["fade"]/R["dur_esc"]
    for (l1,l2,l3) in escenas:
        nf=int(R["dur_esc"]*FPS)
        for i in range(nf):
            t=i/nf
            pin=min(1,t/fade_frac); pout=min(1,(1-t)/fade_frac)
            frame_escena(bg,l1,l2,l3,familia,pin,pout).save(f"{tmp}/f{n:04d}.png"); n+=1
    for i in range(int(R["cierre"]*FPS)):
        t=i/(R["cierre"]*FPS); frame_cierre(bg,familia,min(1,t/0.4)).save(f"{tmp}/f{n:04d}.png"); n+=1
    os.system(f"ffmpeg -hide_banner -loglevel error -y -framerate {FPS} -i {tmp}/f%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart {outname}")
    shutil.rmtree(tmp,ignore_errors=True)
    import subprocess
    d=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",outname],capture_output=True,text=True).stdout.strip()
    return n,float(d)

if __name__=="__main__":
    fr=font("serif",92,400); fi=font("serif-it",112,500)
    esc=[
      ("Hay","señales",[("que no hacen ",fr,(195,202,210)),("ruido.",fi,(150,160,120))]),
      ("Tu cuerpo no","te lo grita.",[("Te lo ",fr,(195,202,210)),("susurra.",fi,(150,160,120))]),
      ("AQUO ordena","lo que sientes",[("para que tenga ",fr,(195,202,210)),("sentido.",fi,(150,160,120))]),
    ]
    n,d=render(esc,"PROFUNDO",3,"AQUO_reel_CALMADO.mp4",ritmo="calmado")
    print(f"✓ CALMADO: {n} frames, {d:.1f}s")
    n,d=render(esc,"PROFUNDO",3,"AQUO_reel_VIVO.mp4",ritmo="vivo")
    print(f"✓ VIVO: {n} frames, {d:.1f}s")
