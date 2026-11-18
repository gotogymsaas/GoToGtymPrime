"""Propone atributos visuales del catalogo a partir de la foto de cada producto.

Usa el mismo endpoint de vision del Coach que la busqueda por foto
(`vendedor/vision.py`, proposito `catalog_attributes`). Por defecto solo
muestra lo que propone; con `--aplicar` llena los atributos que siguen vacios
y los marca como «Propuesto por IA (revisar)» para que alguien del equipo los
confirme en la ficha del panel. Nunca cambia un valor que ya existe.

Cada producto cuesta una llamada al modelo: `--limite` acota cuantos se leen.
"""
from django.core.management.base import BaseCommand, CommandError
from products import atributos
from products.models import Product

from vendedor import coach_client, contrato, imagen, vision

CAMPOS_EN_PRODUCTO = tuple(atributos.CAMPOS)


class Command(BaseCommand):
    help = 'Propone tipo, manga, cuello, ajuste y diseño de cada producto a partir de su foto.'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true',
                            help='Guarda las propuestas en los atributos vacios (sin esto, solo las muestra).')
        parser.add_argument('--producto', type=int, action='append', default=[],
                            help='Solo este producto (se puede repetir).')
        parser.add_argument('--limite', type=int, default=50, help='Maximo de productos a revisar (50).')
        parser.add_argument('--todos', action='store_true',
                            help='Incluye los que ya tienen todos sus atributos.')

    def handle(self, *args, **opciones):
        cliente = coach_client.obtener_cliente()
        if cliente is None:
            raise CommandError('No hay Coach configurado (COACH_API_URL) ni Coach simulado.')

        productos = Product.objects.prefetch_related('media').order_by('sort_order', 'id')
        if opciones['producto']:
            productos = productos.filter(id__in=opciones['producto'])
        revisados = aplicados = 0
        for producto in productos:
            if revisados >= opciones['limite']:
                break
            vacios = [campo for campo in CAMPOS_EN_PRODUCTO if not getattr(producto, campo)]
            if not vacios and not opciones['todos']:
                continue
            foto = producto.primary_image
            if not foto:
                self.stdout.write(f'#{producto.id} {producto.name}: sin foto, se omite.')
                continue
            revisados += 1
            try:
                with foto.open('rb') as archivo:
                    preparada = imagen.preparar(archivo.read())
                descripcion = cliente.describir(
                    vision.armar_solicitud(preparada, 'es', proposito='catalog_attributes'))
            except (OSError, imagen.ImagenInvalida) as error:
                self.stdout.write(self.style.WARNING(f'#{producto.id} {producto.name}: foto ilegible ({error}).'))
                continue
            except (coach_client.CoachNoDisponible, contrato.ContratoInvalido) as error:
                raise CommandError(f'El Coach no describio la foto de #{producto.id}: {error}') from None

            if not descripcion.prenda:
                self.stdout.write(f'#{producto.id} {producto.name}: el modelo no vio una prenda.')
                continue
            propuestos = {c: v for c, v in descripcion.atributos.items() if c in CAMPOS_EN_PRODUCTO}
            nuevos = {c: v for c, v in propuestos.items() if c in vacios}
            colores = ', '.join(descripcion.atributos.get('colors', [])) or '-'
            detalle = ', '.join(f'{c}={v}' for c, v in propuestos.items()) or 'sin atributos'
            self.stdout.write(
                f'#{producto.id} {producto.name}: {detalle} (colores vistos: {colores}; '
                f'confianza {descripcion.confianza:.2f})')
            if opciones['aplicar'] and nuevos:
                for campo, valor in nuevos.items():
                    setattr(producto, campo, valor)
                producto.visual_attributes_origin = atributos.ORIGEN_IA
                producto.save(update_fields=[*nuevos, 'visual_attributes_origin'])
                aplicados += 1

        accion = f'{aplicados} actualizados' if opciones['aplicar'] else 'nada guardado (usa --aplicar)'
        self.stdout.write(self.style.SUCCESS(f'{revisados} productos revisados; {accion}.'))
