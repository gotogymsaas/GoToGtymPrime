"""Version vigente de los terminos del programa de afiliados.

Cuando el texto de `afiliados/terminos.html` cambie de fondo (comision,
plazos, pagos), se sube `VERSION_TERMINOS_AFILIADOS` y se actualiza
`VIGENTE_DESDE`: cada postulacion guarda la version que la persona acepto
(`PerfilAfiliado.terms_version`)."""
from datetime import date
from decimal import Decimal

VERSION_TERMINOS_AFILIADOS = '1.0'
VIGENTE_DESDE = date(2026, 10, 9)

# Comision que los terminos publicados prometen sobre el subtotal. La tasa
# global del programa debe coincidir con ella: si se cambia, hay que actualizar
# el texto y subir la version (el panel de administracion avisa de la
# diferencia).
COMISION_GLOBAL_EN_TERMINOS = Decimal('20.00')
