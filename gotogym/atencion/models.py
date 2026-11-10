"""Solicitudes de atencion humana con radicado verificable.

El radicado se asigna dentro de la misma transaccion que crea la fila, a
partir de su id: si la fila no existe, no hay radicado, y nadie (ni Quantum
Coach) puede anunciar uno que no se haya guardado.

No se guarda la conversacion con la IA: solo lo que la persona escribe en el
formulario y el motivo que elige.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class SolicitudAtencion(models.Model):
    class Motivo(models.TextChoices):
        COMPRA = 'compra', _('Ayuda para comprar')
        TALLA = 'talla', _('Talla o producto')
        PEDIDO = 'pedido', _('Un pedido que ya hice')
        CAMBIO = 'cambio', _('Cambio, devolución o garantía')
        OTRO = 'otro', _('Otro tema')

    class Estado(models.TextChoices):
        ABIERTA = 'abierta', _('Abierta')
        EN_PROCESO = 'en_proceso', _('En proceso')
        CERRADA = 'cerrada', _('Cerrada')

    class Origen(models.TextChoices):
        QUANTUM_COACH = 'quantum_coach', 'Quantum Coach'
        CONTACTO = 'contacto', _('Página de contacto')

    radicado = models.CharField(max_length=20, unique=True, null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='solicitudes_atencion',
    )
    nombre = models.CharField(max_length=120)
    email = models.EmailField()
    motivo = models.CharField(max_length=16, choices=Motivo.choices)
    mensaje = models.TextField(max_length=1000)
    origen = models.CharField(max_length=16, choices=Origen.choices)
    estado = models.CharField(max_length=16, choices=Estado.choices, default=Estado.ABIERTA)
    acepta_contacto = models.BooleanField()
    correo_cliente_enviado = models.BooleanField(default=False)
    correo_equipo_enviado = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creada']
        indexes = [models.Index(fields=['estado', '-creada'], name='atencion_estado_creada')]

    def __str__(self):
        return self.radicado or f'Solicitud {self.pk}'
