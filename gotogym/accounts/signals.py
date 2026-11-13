"""Senales de cuentas que otras apps pueden escuchar sin que `accounts` las
conozca (la regla de capas impide que `accounts` importe apps superiores)."""
from django.dispatch import Signal

# Una persona acepto por primera vez los terminos de la tienda: al registrarse
# con el formulario propio o en su primer acceso con la cuenta GoToGym.
# Argumento: `user`.
perfil_creado = Signal()
