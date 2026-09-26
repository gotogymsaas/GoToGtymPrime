"""Genera los derivados responsivos de las imagenes del sitio.

    python manage.py generar_derivados_imagen
    python manage.py generar_derivados_imagen --forzar

Es idempotente: solo regenera lo que falta o lo que quedo mas viejo que su
origen, asi que puede ejecutarse en cada despliegue sin coste.

El resultado (los .avif/.webp y el manifiesto) se versiona, porque la
imagen de despliegue no ejecuta este paso.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image, ImageOps

from tienda.imagenes import (
    ANCHOS,
    FORMATOS,
    clave_desde_ruta,
    limpiar_cache,
    raiz_derivados,
    raiz_estaticos,
    ruta_manifiesto,
)

EXTENSIONES = {'.jpg', '.jpeg', '.png', '.jfif', '.webp'}

# Calidades elegidas para que la diferencia no se aprecie en pantalla en
# fotografia de producto. AVIF admite mas compresion que WebP a igualdad
# de percepcion.
CALIDAD = {'AVIF': 46, 'WEBP': 72}


class Command(BaseCommand):
    help = 'Crea derivados AVIF/WebP responsivos de las imagenes de catalogo y editoriales.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--forzar', action='store_true',
            help='Regenera tambien los derivados que ya estan al dia.')

    def _origenes(self):
        """(etiqueta, directorio raiz, prefijo dentro del manifiesto)."""
        estaticos = raiz_estaticos()
        medios = Path(settings.MEDIA_ROOT)
        return [
            ('catalogo', estaticos / 'product_media', 'product_media'),
            ('editorial', medios / 'products' / 'Imagenes Home', 'media/products/Imagenes Home'),
        ]

    def handle(self, *args, **opciones):
        forzar = opciones['forzar']
        destino_raiz = raiz_derivados()
        destino_raiz.mkdir(parents=True, exist_ok=True)

        manifiesto = {}
        bytes_origen = 0
        bytes_derivados = 0
        generados = 0
        omitidos = 0

        for etiqueta, raiz, prefijo in self._origenes():
            if not raiz.exists():
                self.stdout.write(self.style.WARNING(
                    f'sin carpeta {etiqueta}: {raiz}'))
                continue

            for origen in sorted(raiz.rglob('*')):
                if not origen.is_file() or origen.suffix.lower() not in EXTENSIONES:
                    continue
                if raiz_derivados() in origen.parents:
                    continue

                relativa = origen.relative_to(raiz).as_posix()
                clave_manifiesto = f'{prefijo}/{relativa}'
                nombre = clave_desde_ruta(clave_manifiesto)

                try:
                    with Image.open(origen) as imagen:
                        # exif_transpose respeta la orientacion de camara;
                        # sin esto una foto vertical sale tumbada.
                        imagen = ImageOps.exif_transpose(imagen)
                        imagen = imagen.convert('RGB')
                        ancho_original, alto_original = imagen.size

                        formatos_generados = {}
                        for extension, formato_pil, _tipo in FORMATOS:
                            anchos_hechos = []
                            for ancho in ANCHOS:
                                if ancho > ancho_original:
                                    continue
                                salida = destino_raiz / f'{nombre}-{ancho}.{extension}'
                                anchos_hechos.append(ancho)

                                if not forzar and salida.exists() and \
                                        salida.stat().st_mtime >= origen.stat().st_mtime:
                                    omitidos += 1
                                    bytes_derivados += salida.stat().st_size
                                    continue

                                alto = max(1, round(alto_original * ancho / ancho_original))
                                copia = imagen.resize((ancho, alto), Image.LANCZOS)
                                copia.save(salida, formato_pil,
                                           quality=CALIDAD[formato_pil], method=6
                                           if formato_pil == 'WEBP' else None)
                                generados += 1
                                bytes_derivados += salida.stat().st_size

                            # Si el original es mas pequeno que el menor de
                            # los anchos, se genera igual en ese unico ancho
                            # para no perder el cambio de formato.
                            if not anchos_hechos:
                                salida = destino_raiz / f'{nombre}-{ancho_original}.{extension}'
                                imagen.save(salida, formato_pil, quality=CALIDAD[formato_pil])
                                anchos_hechos = [ancho_original]
                                generados += 1
                                bytes_derivados += salida.stat().st_size

                            formatos_generados[extension] = anchos_hechos

                except Exception as error:  # imagen corrupta o formato raro
                    self.stdout.write(self.style.WARNING(
                        f'no se pudo procesar {relativa}: {error}'))
                    continue

                bytes_origen += origen.stat().st_size
                manifiesto[clave_manifiesto] = {
                    'nombre': nombre,
                    'ancho': ancho_original,
                    'alto': alto_original,
                    'formatos': formatos_generados,
                }

        with open(ruta_manifiesto(), 'w', encoding='utf-8') as archivo:
            json.dump(manifiesto, archivo, indent=2, ensure_ascii=False, sort_keys=True)
        limpiar_cache()

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{len(manifiesto)} imagenes en el manifiesto '
            f'({generados} derivados nuevos, {omitidos} ya al dia)'))
        if bytes_origen:
            mb_origen = bytes_origen / 1048576.0
            mb_derivados = bytes_derivados / 1048576.0
            self.stdout.write(
                f'origen {mb_origen:.1f} MB  ->  derivados {mb_derivados:.1f} MB '
                f'en {len(ANCHOS)} anchos y {len(FORMATOS)} formatos')
            self.stdout.write(
                'el navegador descarga UNO por imagen, no todos: '
                'el mayor ahorro esta en servir 400-960 px donde antes iba el original'
            )
