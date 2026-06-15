# -*- coding: utf-8 -*-
"""
AQUO · Animación PLUMA — escritura manuscrita trazo a trazo sobre papel.
El texto caligráfico (Allura) se revela de izquierda a derecha, como si
una pluma invisible lo escribiera. Sobre una plantilla de papel real.
"""
import os, shutil, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from aquo_reel import W,H,NAVY,OLIVA,MARFIL,AGUA, font
from aquo_motor import frame_cierre, ease, RITMOS, FPS

TINTA=(28,42,66)  # azul tinta profunda, no negro puro

def _pluma_font(size): return ImageFont.truetype("fonts/Allura-Regular.ttf", size)
def _sub_font(size, familia="PAPEL"):
    f=ImageFont.truetype("fonts/CormorantGaramond[wght].ttf", size)
    try: f.set_variation_by_axes([500])
    except: pass
    return f

def render_pluma(lineas_manuscritas, subtexto, salida, papel="papel_pluma.png", ritmo="calmado"):
    """
    lineas_manuscritas: lista de strings (se escriben a pluma, una bajo otra)
    subtexto: línea final en Cormorant (firma/cierre del mensaje), puede ser ''
    """
    R=RITMOS[ritmo]
    base=Image.open(papel).convert("RGB")
    # 1) Renderizo el texto manuscrito COMPLETO en una capa aparte
    capa=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(capa)
    fnt=_pluma_font(140)
    # centrado vertical en la zona de papel (~centro)
    interlinea=160
    total_h=len(lineas_manuscritas)*interlinea
    y0=H//2 - total_h//2 - 40
    bboxes=[]
    for i,ln in enumerate(lineas_manuscritas):
        w=d.textlength(ln,font=fnt)
        x=W/2-w/2; y=y0+i*interlinea
        d.text((x,y),ln,font=fnt,fill=(*TINTA,255))
        bboxes.append((x,y,w))
    # subtexto Cormorant debajo
    if subtexto:
        sf=_sub_font(58); sw=d.textlength(subtexto,font=sf)
        d.text((W/2-sw/2, y0+total_h+30), subtexto, font=sf, fill=(90,98,82,255))
    # inclinación cursiva: shear horizontal de la capa manuscrita (~9°)
    shear=-0.16
    capa=capa.transform((W,H), Image.AFFINE, (1,shear,-shear*H/2, 0,1,0), resample=Image.BICUBIC)
    # 2) Animo: máscara que revela de izq a der, línea por línea
    tmp="_pluma"; shutil.rmtree(tmp,ignore_errors=True); os.makedirs(tmp)
    n=0
    nf_write=int((R["dur_esc"]*len(lineas_manuscritas))*FPS*0.5)
    nf_hold=int(R["dur_esc"]*FPS*0.7)
    # ancho total a "escribir" = suma de anchos de línea
    total_w=sum(b[2] for b in bboxes)
    for i in range(nf_write):
        t=i/nf_write
        revealed=ease(t)*total_w
        mask=Image.new("L",(W,H),0); md=ImageDraw.Draw(mask)
        acc=0
        for (x,y,w) in bboxes:
            if revealed>=acc+w:
                md.rectangle([0,y-20,W,y+interlinea],fill=255)
            elif revealed>acc:
                px=x+(revealed-acc)
                md.rectangle([0,y-20,int(px)+8,y+interlinea],fill=255)
            acc+=w
        # subtexto aparece al final
        if t>0.9:
            md.rectangle([0,y0+total_h,W,H],fill=int(255*ease((t-0.9)/0.1)))
        frame=base.copy().convert("RGBA")
        capa_rec=Image.new("RGBA",(W,H),(0,0,0,0))
        capa_rec.paste(capa,(0,0),Image.composite(capa.split()[3],Image.new("L",(W,H),0),mask))
        frame.alpha_composite(capa_rec)
        frame.convert("RGB").save(f"{tmp}/f{n:04d}.png"); n+=1
    # hold: texto completo
    full=base.copy().convert("RGBA"); full.alpha_composite(capa)
    for i in range(nf_hold):
        full.convert("RGB").save(f"{tmp}/f{n:04d}.png"); n+=1
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-framerate",str(FPS),
                    "-i",f"{tmp}/f%04d.png","-c:v","libx264","-pix_fmt","yuv420p","-crf","18",
                    "-movflags","+faststart",salida],check=True)
    shutil.rmtree(tmp,ignore_errors=True)
    print(f"✓ {salida} (pluma)")

if __name__=="__main__":
    # frame de prueba (media escritura)
    render_pluma(["Respira.","Hoy basta","con un paso."],"— AQUO","_test_pluma_full.mp4",ritmo="calmado")
