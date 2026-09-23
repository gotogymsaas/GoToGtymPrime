from django.db import models


class EventoAnalitica(models.Model):
    """Un evento de uso del sitio, sin datos personales.

    La tabla responde preguntas de producto: cuanta gente pasa del Home a
    una ficha, si el buscador de la barra se usa, que intencion se elige.
    Para eso basta con poder agrupar por sesion, asi que no guarda usuario,
    correo ni nombre: solo un hash de la clave de sesion, que rota cuando
    rota la sesion y no sirve para identificar a nadie fuera de aqui.

    El hash tambien evita almacenar la clave de sesion en claro, que es una
    credencial: quien leyera esta tabla podria suplantar sesiones activas.
    """

    nombre = models.CharField(max_length=64, db_index=True)
    ruta = models.CharField(max_length=300, blank=True)
    sesion = models.CharField(max_length=64, db_index=True, blank=True)
    autenticado = models.BooleanField(default=False)
    propiedades = models.JSONField(default=dict, blank=True)
    creado = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'evento de analitica'
        verbose_name_plural = 'eventos de analitica'
        ordering = ('-creado',)
        indexes = [
            models.Index(fields=['nombre', 'creado']),
        ]

    def __str__(self):
        return f'{self.nombre} @ {self.creado:%Y-%m-%d %H:%M}'
