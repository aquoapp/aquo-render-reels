# AQUO · Servicio de render de reels

Este es el servidor que monta tus reels (.mp4) en la nube. Tu motor de Python
+ ffmpeg, listo para que **Make lo llame** y tú no toques nada en el día a día.

## Qué hace
1. Recibe una orden por HTTP (POST /render) con el guion del reel.
2. Monta el .mp4 con tu motor (capa 1 editorial o capa 2 con tus clips).
3. Sube el .mp4 a tu Drive (carpeta REELS_AQUO).
4. Llama al webhook ENTREGA de Make → te llega a Telegram con tipo=reel.

## Por qué NO va en Netlify
Netlify no tiene ffmpeg ni soporta renders largos. Este servicio usa Docker con
ffmpeg incluido. Vive en Render.com (plan gratis para empezar).

## CÓMO LO ARRANCAS (una sola vez — luego nunca más entras)

### Paso 1 — Subir el código a GitHub
(Yo te doy el ZIP; tú lo subes a un repo nuevo, o yo te guío para hacerlo.)

### Paso 2 — Crear el servicio en Render
1. Entra en https://render.com y regístrate (gratis, con tu Google).
2. New → Web Service → conecta el repo de GitHub.
3. Render detecta el Dockerfile solo. Plan: Free.

### Paso 3 — Pegar 4 variables de entorno (en Render, sección Environment)
- `WEBHOOK_ENTREGA` = https://hook.eu1.make.com/iebp5goalo1a39bsz04ib6aump4kkjx8
- `DRIVE_FOLDER_ID` = 1crIrrHpiZu3PgX8ovhIWAqKIcNC9Rtby   (carpeta REELS_AQUO)
- `RENDER_TOKEN` = (una contraseña que inventes; Make la mandará para seguridad)
- `GOOGLE_SA_JSON` = (el JSON de una cuenta de servicio de Google — te guío para crearla)

### Paso 4 — Deploy
Render construye y arranca. Te da una URL tipo:
  https://aquo-render-reels.onrender.com

Esa URL es la que Make llamará. Me la pasas y yo conecto Make.

## Cómo se llama (lo hará Make, no tú)
```
POST https://tu-servicio.onrender.com/render
Header: X-AQUO-TOKEN: (tu RENDER_TOKEN)
Body (capa 1, reel editorial):
{
  "capa": 1,
  "pieza": "reel_p015",
  "caption": "Tu vida no está desordenada... #aquo",
  "guion": [
    {"l1":"Tu vida","l2":"no está","l3":"desordenada. *Solo necesita orden.*"}
  ],
  "familia": "PROFUNDO",   // o "MARFIL" o null (varía solo)
  "ritmo": "sereno",       // o "calmado"/"vivo"/null
  "seed": 7                // o null
}
Body (capa 2, sobre un clip real):
{
  "capa": 2,
  "clip": "c01_vaso_agua.mp4",
  "pieza": "reel_agua",
  "caption": "Empieza el día con un vaso de agua. #aquo",
  "guion": {"l1":"Empieza el día","l2":"con un vaso","l3":"de *agua.*"},
  "familia": "PROFUNDO",
  "ritmo": "sereno"
}
```

## Nota importante
Un reel tarda ~1-2 minutos en montarse (cientos de fotogramas). El servicio
responde al instante (202 "montando") y termina en segundo plano; cuando acaba,
te llega solo a Telegram. No hay que esperar mirando.

## Clips disponibles (capa 2)
En motor/clips/ van tus clips de Grok. De muestra: c01_vaso_agua, c02_agua_sirviendose,
c04_manos_taza, c13_marmol_mar, c15_chillout. Cuando se acaben, se generan más con Grok.
