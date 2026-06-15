# -*- coding: utf-8 -*-
"""AQUO · Motor de reels — núcleo. Olivo ampliado + sin filo."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random

W, H = 1080, 1920
NAVY=(16,42,67); AGUA=(91,167,199); ARENA=(233,226,214); MARFIL=(247,244,239)
OLIVA=(122,127,105); TIERRA=(201,178,155); AMBAR=(201,162,75)
FONTS="fonts/"

# cache de olivos recortados al contenido
_olivo_cache={}
def _olivo_recortado(familia):
    if familia in _olivo_cache: return _olivo_cache[familia]
    src="olivo_navy.png" if familia=="PROFUNDO" else "olivo_marfil.png"
    o=Image.open(src).convert("RGBA")
    bbox=o.split()[3].getbbox()      # recorta a las hojas reales
    o=o.crop(bbox)
    _olivo_cache[familia]=o
    return o

def font(kind, size, weight=400):
    fmap={"serif":"CormorantGaramond[wght].ttf","serif-it":"CormorantGaramond-Italic[wght].ttf","display":"Outfit[wght].ttf"}
    f=ImageFont.truetype(FONTS+fmap[kind],size)
    try:f.set_variation_by_axes([weight])
    except Exception:pass
    return f

def fondo(familia="PROFUNDO", seed=0):
    random.seed(seed)
    if familia=="PROFUNDO": top,bottom=(14,33,54),(6,20,38)
    else: top,bottom=(249,246,241),(235,228,216)
    img=Image.new("RGB",(W,H)); px=img.load()
    for y in range(H):
        t=y/H; t=t*t*(3-2*t)
        r=int(top[0]+(bottom[0]-top[0])*t); g=int(top[1]+(bottom[1]-top[1])*t); b=int(top[2]+(bottom[2]-top[2])*t)
        for x in range(W): px[x,y]=(r,g,b)
    noise=Image.effect_noise((W,H),14).convert("L")
    noise=noise.point(lambda v:int((v-128)*0.16+128))
    img=Image.blend(img,Image.merge("RGB",(noise,noise,noise)),0.045)
    return img

def pon_olivo(img, familia="PROFUNDO", escala=0.62):
    """escala = fracción del ancho del lienzo que ocupa el olivo (más grande ahora)."""
    olivo=_olivo_recortado(familia)
    tw=int(W*escala); ratio=tw/olivo.width
    olivo=olivo.resize((tw,int(olivo.height*ratio)),Image.LANCZOS)
    alpha=olivo.split()[3]
    shadow=Image.new("RGBA",(W,H),(0,0,0,0))
    sh_col=(0,0,0,110) if familia=="PROFUNDO" else (95,82,58,75)
    sh=Image.new("RGBA",olivo.size,(0,0,0,0))
    sh.paste(Image.new("RGBA",olivo.size,sh_col),(0,0),alpha)
    sh=sh.filter(ImageFilter.GaussianBlur(28))
    # anclado arriba-derecha, asoma un poco por arriba
    ox,oy=W-tw, -int(olivo.height*0.06)
    shadow.paste(sh,(ox-60,oy+80),sh)
    img=img.convert("RGBA"); img.alpha_composite(shadow); img.alpha_composite(olivo,(ox,oy))
    return img.convert("RGB")

def dibuja_baseline(draw,x,by,palabra,fnt,fill):
    asc,desc=fnt.getmetrics()
    draw.text((x,by-asc),palabra,font=fnt,fill=fill)
    return draw.textlength(palabra,font=fnt)

def linea_mixta(draw,by,tokens,cx=W//2,gap=14):
    total=sum(draw.textlength(t[0],font=t[1]) for t in tokens)+(len(tokens)-1)*gap
    x=cx-total/2
    for txt,fnt,col in tokens: x+=dibuja_baseline(draw,x,by,txt,fnt,col)+gap

def escena(img,l1,l2,l3_tokens,familia="PROFUNDO"):
    draw=ImageDraw.Draw(img)
    c_tenue=(195,202,210) if familia=="PROFUNDO" else (92,96,82)
    c_pleno=MARFIL if familia=="PROFUNDO" else NAVY
    f_reg=font("serif",92,400); f_bold=font("serif",150,700)
    base=960
    linea_mixta(draw,base-150,[(l1,f_reg,c_tenue)])
    linea_mixta(draw,base+20,[(l2,f_bold,c_pleno)])
    linea_mixta(draw,base+185,l3_tokens)
    return img

if __name__=="__main__":
    fr=font("serif",92,400); fi=font("serif-it",112,500)
    a=fondo("PROFUNDO",3); a=pon_olivo(a,"PROFUNDO",escala=0.66)
    a=escena(a,"Los días en que","todo cuesta",[("un poco ",fr,(195,202,210)),("más.",fi,(150,160,120))],"PROFUNDO")
    a.save("test_profundo.png"); print("✓ test_profundo.png (olivo ampliado + sin filo)")
