# Tipografía de origen (TT Norms Pro)

Estos `.otf` son los **archivos fuente**, no los que sirve el sitio.

Vivían en `gotogym/static/Tipografia/`, de donde `collectstatic` los
copiaba enteros y WhiteNoise los publicaba: 3,8 MB de una tipografía
comercial descargables por cualquiera, de los cuales el sitio solo usaba
dos caras.

Lo que se sirve son dos subconjuntos en `woff2`, declarados en
`gotogym/static/css/style.css`:

| Cara | Origen | Servido |
|---|---|---|
| Regular 400 | `Cuerpo de Mensaje/TT Norms Pro Regular.otf` | `static/fonts/tt-norms/tt-norms-regular.woff2` |
| ExtraBold 800 | `Titulo/TT Norms Pro ExtraBold.otf` | `static/fonts/tt-norms/tt-norms-extrabold.woff2` |

## Regenerar un subconjunto

```bash
python -m fontTools.subset "design/tipografia-fuente/Titulo/TT Norms Pro ExtraBold.otf" \
  --unicodes="U+0000-00FF,U+0100-017F,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2190-21FF,U+2212,U+2215,U+FEFF,U+FFFD" \
  --layout-features="kern,liga,clig,calt,ccmp,locl,mark,mkmk" \
  --flavor=woff2 \
  --output-file="gotogym/static/fonts/tt-norms/tt-norms-extrabold.woff2"
```

El rango cubre español, inglés y portugués, más la puntuación y las
flechas (`→ ↗ ←`) que usan las plantillas. Si se añade un idioma con otro
alfabeto hay que ampliarlo.

## Licencia

TT Norms Pro es una tipografía comercial. El uso web requiere licencia
web propia, distinta de la licencia de escritorio; convertir a `woff2` no
cambia esa condición. Mientras no esté confirmada, el sustituto digital
del sistema es Outfit, que ya se sirve desde `static/fonts/outfit/`.
