"""Banco de afirmaciones sobre las prendas.

Toda cifra o promesa sobre un textil que se publique en el sitio tiene que
estar aqui, con su fuente y la fecha desde la que vale. Lo que no figura en
`APROBADAS` no se afirma; lo que figura en `PROHIBIDAS` no puede aparecer en
ninguna plantilla (lo comprueba `test_afirmaciones.py`).

"""
from collections import namedtuple

Afirmacion = namedtuple('Afirmacion', 'id texto fuente vigente_desde pagina')

# Hoy no hay afirmaciones propias aprobadas: toda cifra sobre un textil de GoToGym
# entra aqui con su fuente y vigencia antes de publicarse.
APROBADAS = ()

PROHIBIDAS = (
    'secado rápido', 'secado rapido',
    'protección solar', 'proteccion solar',
    'repelencia sobresaliente', 'repele el agua', 'sin importar las condiciones',
    'libre de irritaciones', 'ph equilibrado', 'seguro para la piel',
    'mantén la forma', 'manten la forma',
    'regulación térmica', 'regulacion termica',
    'ecológic', 'ecologic', 'huella ambiental',
    'antimicrobian',
)
