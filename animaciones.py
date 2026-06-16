# -*- coding: utf-8 -*-
"""
AQUO · Motor de reels — CATÁLOGO DE ANIMACIONES DE TEXTO.
Cada animación recibe el fondo (con olivo) y dibuja el texto de la escena
con un estilo de aparición distinto. Todas respetan baseline + colores de marca.

Animaciones:
  fundido          (ya existía) — aparición suave de las 3 líneas
  maquina          — letra a letra con cursor (typewriter)
  suben            — cada palabra entra desde abajo con velo
  revelado         — las 3 líneas aparecen una a una con barrido de luz agua
"""
import os, shutil, subprocess, math
from PIL import Image, ImageDraw, ImageFilter
from aquo_reel import (W,H,NAVY,AGUA,MARFIL,OLIVA, font, fondo, pon_olivo,
                       dibuja_baseline, linea_mixta)
from aquo_motor import _tokens3, frame_cierre, ease, RITMOS, FPS

def _colores(familia):
    tenue=(195,202,210) if familia=="PROFUNDO" else (92,96,82)
    pleno=MARFIL if familia=="PROFUNDO" else NAVY
    return tenue, pleno

MARGEN_SEG=96  # debe coincidir con aquo_reel.linea_mixta

def _fit_fonts(draw, e, familia, f_reg, f_bold):
    """Fix 3A para animaciones que dibujan con ancho propio (maquina/suben/deslizan).
    Calcula el ancho de las 3 líneas con las fuentes nominales; si alguna supera
    el ancho útil, encoge f_reg y f_bold por el MISMO factor (la línea más ancha
    manda) para que las 3 queden coherentes y ninguna se salga. Si todo cabía,
    devuelve las fuentes intactas."""
    max_w=W-2*MARGEN_SEG
    w1=draw.textlength(e["l1"],font=f_reg)
    w2=draw.textlength(e["l2"],font=f_bold)
    l3_tokens=_tokens3(e["l3"],familia)
    w3=sum(draw.textlength(tk[0],font=tk[1]) for tk in l3_tokens)+(max(0,len(l3_tokens)-1))*14
    peor=max(w1,w2,w3)
    factor=1.0
    if peor>max_w and peor>0:
        factor=max_w/peor
        f_reg=f_reg.font_variant(size=max(1,int(f_reg.size*factor)))
        f_bold=f_bold.font_variant(size=max(1,int(f_bold.size*factor)))
    return f_reg, f_bold, factor

def _tokens3_fit(e, familia, factor):
    """Tokens de la línea 3 con el factor de encogido de la escena aplicado."""
    toks=_tokens3(e["l3"],familia)
    if factor>=0.999: return toks
    return [(t[0], t[1].font_variant(size=max(1,int(t[1].size*factor))), t[2]) for t in toks]

# ── helpers de dibujo con alpha ──────────────────────────────
def _linea_alpha(draw, by, tokens, alpha, cx=W//2, gap=14):
    a=int(255*ease(max(0,min(1,alpha))))
    toks=[(t[0],t[1],(t[2][0],t[2][1],t[2][2],a)) for t in tokens]
    linea_mixta(draw,by,toks,cx=cx,gap=gap)

# ════════════════════════════════════════════════════════════
#  ANIMACIÓN: MÁQUINA DE ESCRIBIR (letra a letra, con cursor)
# ════════════════════════════════════════════════════════════
def anim_maquina(bg, e, familia, t):
    """t = progreso 0..1 de la escena. Escribe las 3 líneas en secuencia."""
    tenue,pleno=_colores(familia)
    f_reg=font("serif",92,400); f_bold=font("serif",150,700)
    base=960
    img=bg.copy().convert("RGBA"); ov=Image.new("RGBA",(W,H),(0,0,0,0)); draw=ImageDraw.Draw(ov)
    f_reg,f_bold,_fac=_fit_fonts(draw,e,familia,f_reg,f_bold)
    # texto plano de cada línea
    l1=e["l1"]; l2=e["l2"]
    l3_tokens=_tokens3_fit(e,familia,_fac)
    l3_plano="".join(tk[0] for tk in l3_tokens)
    full=l1+l2+l3_plano
    total_chars=len(full)
    # fase de escritura ocupa el 88% del tiempo (más lenta, legible); resto fijo
    write_t=min(1, t/0.88)
    shown=int(total_chars*write_t)
    # cuántos chars por línea
    n1=min(shown,len(l1)); rem=shown-len(l1)
    n2=max(0,min(rem,len(l2))); rem2=rem-len(l2)
    n3=max(0,min(rem2,len(l3_plano)))
    cursor_visible=(int(t*FPS*0.9)%2==0) and write_t<1
    def draw_line(by,texto,fnt,col,nchars,with_cursor):
        sub=texto[:nchars]
        if not sub and not with_cursor: return
        wsub=draw.textlength(sub,font=fnt)
        wcur=draw.textlength("|",font=fnt) if with_cursor else 0
        x=W/2-(wsub+wcur)/2
        if sub:
            asc,_=fnt.getmetrics(); draw.text((x,by-asc),sub,font=fnt,fill=col)
        if with_cursor and cursor_visible:
            asc,_=fnt.getmetrics(); draw.text((x+wsub,by-asc),"|",font=fnt,fill=col)
    # línea activa = donde está el cursor
    draw_line(base-150,l1,f_reg,(*tenue,255),n1, 0<shown<=len(l1))
    if shown>len(l1):
        draw_line(base+20,l2,f_bold,(*pleno,255),n2, len(l1)<shown<=len(l1)+len(l2))
    if shown>len(l1)+len(l2):
        # línea 3 con sus colores por token
        sub_n=n3; x_acc=0
        # reconstruyo respetando tokens y colores
        parts=[]; cnt=0
        for txt,fnt,col in l3_tokens:
            take=max(0,min(len(txt),sub_n-cnt)); cnt+=len(txt)
            parts.append((txt[:take],fnt,col))
        wline=sum(draw.textlength(p[0],font=p[1]) for p in parts)
        cur=(shown>len(l1)+len(l2))
        wcur=draw.textlength("|",font=f_reg) if cur else 0
        x=W/2-(wline+wcur)/2
        for txt,fnt,col in parts:
            if txt:
                asc,_=fnt.getmetrics(); draw.text((x,base+185-asc),txt,font=fnt,fill=(*col,255))
                x+=draw.textlength(txt,font=fnt)
        if cur and cursor_visible:
            asc,_=f_reg.getmetrics(); draw.text((x,base+185-asc),"|",font=f_reg,fill=(*tenue,255))
    img.alpha_composite(ov); return img.convert("RGB")

# ════════════════════════════════════════════════════════════
#  ANIMACIÓN: PALABRAS QUE SUBEN (cada palabra entra desde abajo)
# ════════════════════════════════════════════════════════════
def anim_suben(bg, e, familia, t):
    tenue,pleno=_colores(familia)
    f_reg=font("serif",92,400); f_bold=font("serif",150,700)
    base=960
    img=bg.copy().convert("RGBA"); ov=Image.new("RGBA",(W,H),(0,0,0,0)); draw=ImageDraw.Draw(ov)
    f_reg,f_bold,_fac=_fit_fonts(draw,e,familia,f_reg,f_bold)
    # construyo lista de "unidades" (palabra, fuente, color, línea_y)
    unidades=[]
    for w in e["l1"].split(" "): unidades.append((w,f_reg,tenue,base-150))
    for w in e["l2"].split(" "): unidades.append((w,f_bold,pleno,base+20))
    for txt,fnt,col in _tokens3_fit(e,familia,_fac):
        for w in txt.split(" "):
            if w: unidades.append((w,fnt,col,base+185))
    n=len(unidades)
    # cada palabra entra escalonada
    stagger=0.5/n if n else 0
    # agrupo por línea para centrar
    lineas={}
    for i,(w,fnt,col,ly) in enumerate(unidades):
        lineas.setdefault(ly,[]).append((i,w,fnt,col))
    fade_out=min(1,(1-t)/0.18)
    for ly,items in lineas.items():
        total=sum(draw.textlength(it[1]+" ",font=it[2]) for it in items)
        x=W/2-total/2
        for i,w,fnt,col in items:
            p=max(0,min(1,(t-i*stagger)/0.28))
            a=int(255*ease(p)*ease(max(0,min(1,fade_out))))
            dy=int(26*(1-ease(p)))
            asc,_=fnt.getmetrics()
            draw.text((x,ly-asc+dy),w,font=fnt,fill=(*col,a))
            x+=draw.textlength(w+" ",font=fnt)
    img.alpha_composite(ov); return img.convert("RGB")

# ════════════════════════════════════════════════════════════
#  ANIMACIÓN: REVELADO POR LÍNEA (línea a línea + barrido luz agua)
# ════════════════════════════════════════════════════════════
def anim_revelado(bg, e, familia, t):
    tenue,pleno=_colores(familia)
    f_reg=font("serif",92,400); f_bold=font("serif",150,700)
    base=960
    img=bg.copy().convert("RGBA"); ov=Image.new("RGBA",(W,H),(0,0,0,0)); draw=ImageDraw.Draw(ov)
    lineas=[(base-150,[(e["l1"],f_reg,tenue)]),
            (base+20,[(e["l2"],f_bold,pleno)]),
            (base+185,_tokens3(e["l3"],familia))]
    fade_out=min(1,(1-t)/0.18)
    for idx,(by,toks) in enumerate(lineas):
        start=idx*0.18
        p=max(0,min(1,(t-start)/0.32))
        a=ease(p)*ease(max(0,min(1,fade_out)))
        _linea_alpha(draw,by,toks,a)
        # barrido de luz agua bajo la línea que acaba de aparecer
        if 0.1<p<0.9:
            wline=sum(draw.textlength(tk[0],font=tk[1]) for tk in toks)+(len(toks)-1)*14
            lx=W/2-wline/2; ly=by+22
            sweep=int(wline*p)
            for dx in range(max(0,sweep-60),sweep):
                aa=int(160*(1-abs(dx-sweep+30)/60))
                if 0<=lx+dx<W and aa>0:
                    draw.line([(lx+dx,ly),(lx+dx,ly+3)],fill=(*AGUA,aa))
    img.alpha_composite(ov); return img.convert("RGB")

# ════════════════════════════════════════════════════════════
#  ANIMACIÓN: DESLIZAN (palabras entran desde izq/der y forman la frase)
# ════════════════════════════════════════════════════════════
def anim_deslizan(bg, e, familia, t):
    tenue,pleno=_colores(familia)
    f_reg=font("serif",92,400); f_bold=font("serif",150,700)
    base=960
    img=bg.copy().convert("RGBA"); ov=Image.new("RGBA",(W,H),(0,0,0,0)); draw=ImageDraw.Draw(ov)
    f_reg,f_bold,_fac=_fit_fonts(draw,e,familia,f_reg,f_bold)
    # unidades por línea
    def units_de_linea(ly, tokens):
        us=[]
        for txt,fnt,col in tokens:
            for w in txt.split(" "):
                if w: us.append([w,fnt,col,ly])
        return us
    lineas=[units_de_linea(base-150,[(e["l1"],f_reg,tenue)]),
            units_de_linea(base+20,[(e["l2"],f_bold,pleno)]),
            units_de_linea(base+185,_tokens3_fit(e,familia,_fac))]
    fade_out=min(1,(1-t)/0.16)
    gi=0  # índice global para alternar lado y escalonar
    for items in lineas:
        # posiciones finales centradas
        total=sum(draw.textlength(it[0]+" ",font=it[1]) for it in items)
        x0=W/2-total/2; xacc=x0
        for it in items:
            w,fnt,col,ly=it
            wpix=draw.textlength(w+" ",font=fnt)
            xfin=xacc
            # alterna lado: pares desde izquierda, impares desde derecha
            desde_izq=(gi%2==0)
            start_x = -400 if desde_izq else W+200
            stagger=gi*0.05
            p=max(0,min(1,(t-stagger)/0.34))
            ep=ease(p)
            x=start_x+(xfin-start_x)*ep
            a=int(255*ep*ease(max(0,min(1,fade_out))))
            asc,_=fnt.getmetrics()
            draw.text((x,ly-asc),w,font=fnt,fill=(*col,a))
            xacc+=wpix; gi+=1
    img.alpha_composite(ov); return img.convert("RGB")

ANIMS={"maquina":anim_maquina,"suben":anim_suben,"revelado":anim_revelado,"deslizan":anim_deslizan}

def render_anim(escenas, salida, anim="maquina", familia="PROFUNDO", ritmo="sereno", seed=3, escala_olivo=0.54):
    fn=ANIMS[anim]; R=RITMOS[ritmo]
    tmp="_anim"; shutil.rmtree(tmp,ignore_errors=True); os.makedirs(tmp)
    bg=fondo(familia,seed); bg=pon_olivo(bg,familia,escala=escala_olivo)
    n=0
    for e in escenas:
        nf=int(R["dur_esc"]*FPS)
        for i in range(nf):
            t=i/nf
            fn(bg,e,familia,t).save(f"{tmp}/f{n:04d}.png"); n+=1
    for i in range(int(R["cierre"]*FPS)):
        t=i/(R["cierre"]*FPS); frame_cierre(bg,familia,min(1,t/0.4)).save(f"{tmp}/f{n:04d}.png"); n+=1
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-framerate",str(FPS),
                    "-i",f"{tmp}/f%04d.png","-c:v","libx264","-pix_fmt","yuv420p","-crf","18",
                    "-movflags","+faststart",salida],check=True)
    shutil.rmtree(tmp,ignore_errors=True)
    print(f"✓ {salida} ({anim})")
