from django.db import models
from django.utils import timezone


class EstadoTarea(models.TextChoices):
    PENDIENTE = 'pendiente', 'Pendiente'
    EN_CURSO = 'en_curso', 'En curso'
    HECHA = 'hecha', 'Hecha'
    FALLIDA = 'fallida', 'Fallida'


class TareaPendiente(models.Model):
    """Una llamada a una funcion de modulo que el trabajador ejecuta fuera de
    la peticion web.

    Guarda la ruta de la funcion y sus argumentos (JSON), no el resultado: lo
    que importa es el efecto. `ultimo_error` nunca lleva datos personales (ver
    `ejecucion.resumir_error`)."""

    ruta = models.CharField(max_length=255)
    # {"args": [...], "kwargs": {...}}
    argumentos = models.JSONField(default=dict, blank=True)
    estado = models.CharField(
        max_length=12, choices=EstadoTarea.choices, default=EstadoTarea.PENDIENTE, db_index=True,
    )
    intentos = models.PositiveSmallIntegerField(default=0)
    maximo_intentos = models.PositiveSmallIntegerField(default=5)
    proximo_intento = models.DateTimeField(default=timezone.now, db_index=True)
    iniciada = models.DateTimeField(
        null=True, blank=True,
        help_text='Cuando un trabajador la tomo; si se pierde, otra corrida la recupera.',
    )
    ultimo_error = models.CharField(max_length=500, blank=True)
    creada = models.DateTimeField(default=timezone.now)
    terminada = models.DateTimeField(null=True, blank=True)
    clave_idempotencia = models.CharField(max_length=190, null=True, blank=True, unique=True)

    class Meta:
        verbose_name = 'tarea pendiente'
        verbose_name_plural = 'tareas pendientes'
        ordering = ('proximo_intento', 'pk')
        indexes = [models.Index(fields=['estado', 'proximo_intento'])]
        permissions = [('retry_tarea', 'Puede reintentar tareas fallidas')]

    def __str__(self):
        return f'{self.ruta} ({self.estado})'


class TareaPeriodica(models.Model):
    """Una tarea que debe correr cada cierto tiempo. El catalogo vive en
    codigo (`catalogo.py`) y se sincroniza con esta tabla; aqui solo se
    guarda cuando corrio por ultima vez y si esta activa."""

    nombre = models.CharField(max_length=80, unique=True)
    ruta = models.CharField(max_length=255)
    intervalo_segundos = models.PositiveIntegerField()
    ultima_ejecucion = models.DateTimeField(null=True, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'tarea periódica'
        verbose_name_plural = 'tareas periódicas'
        ordering = ('nombre',)

    def __str__(self):
        return self.nombre


class LatidoTrabajador(models.Model):
    """Una sola fila: cuando termino su ultimo ciclo el trabajador. Sirve para
    saber desde fuera si el trabajador sigue vivo."""

    ultimo_ciclo = models.DateTimeField()

    class Meta:
        verbose_name = 'latido del trabajador'
        verbose_name_plural = 'latido del trabajador'

    def __str__(self):
        return f'{self.ultimo_ciclo:%Y-%m-%d %H:%M:%S}'


class EfectoAplicado(models.Model):
    """Marca de que una tarea ya produjo su efecto externo (un correo).

    Pertenece a una ejecucion concreta (`tarea`), no a los argumentos: un
    reintento de la misma tarea no repite el efecto, pero un hecho nuevo con
    los mismos argumentos (una segunda baja del mismo afiliado) es otra tarea
    y si se envia. Se borra junto con la tarea al purgarla."""

    tarea = models.ForeignKey(TareaPendiente, on_delete=models.CASCADE, related_name='efectos')
    nombre = models.CharField(max_length=120)
    creado = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'efecto aplicado'
        verbose_name_plural = 'efectos aplicados'
        constraints = [
            models.UniqueConstraint(fields=['tarea', 'nombre'], name='tareas_efecto_unico'),
        ]

    def __str__(self):
        return f'{self.nombre} (tarea {self.tarea_id})'
