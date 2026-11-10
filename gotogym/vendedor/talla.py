"""Orientacion de talla a partir de las medidas que el cliente confirmo.

Compara cada medida con la guia de tallas GENERAL de la tienda
(`tienda.catalog.SIZE_GUIDE`, medidas del cuerpo, no de la prenda). Al Coach
solo viaja la talla que corresponde a cada dimension, nunca los centimetros.

Limites honestos:
- La guia es una referencia de mercado, no la ficha de cada prenda. El
  resultado se rotula `general_size_guide` y el vendedor debe decirlo.
- Si las dimensiones apuntan a tallas distintas no se elige por la persona:
  se informa la discrepancia (`suggestion` = None).
- Medidas de mas de 6 meses no se usan.
- El ajuste por prenda (motor QAF) necesita medidas de cada prenda, que hoy
  no existen en el catalogo.
"""
from decimal import Decimal

from django.utils import timezone
from tienda.catalog import SIZE_GUIDE, SIZE_ORDER

from .models import TailoringMeasurement

# Medida del cliente -> columna de la guia.
DIMENSIONES = {"chest_cm": "busto", "waist_cm": "cintura", "hip_cm": "cadera"}
SOURCE = "general_size_guide"


def _rango(texto):
    bajo, alto = texto.replace("–", "-").split("-")
    return Decimal(bajo), Decimal(alto)


def _talla_para(columna, valor):
    """Talla de la guia cuyo rango contiene `valor`. Entre dos rangos
    (p. ej. 69,5 cuando S llega a 69 y M empieza en 70) se elige la mayor,
    la opcion conservadora para ropa ceñida. Fuera de la guia: None."""
    tallas = [t for t in SIZE_ORDER if t in SIZE_GUIDE]
    for i, talla in enumerate(tallas):
        bajo, alto = _rango(SIZE_GUIDE[talla][columna])
        if bajo <= valor <= alto:
            return talla
        siguiente = tallas[i + 1] if i + 1 < len(tallas) else None
        if siguiente and alto < valor < _rango(SIZE_GUIDE[siguiente][columna])[0]:
            return siguiente
    return None


def orientacion(user, now=None):
    """Dict para el Coach o None si no hay medidas vigentes."""
    medida = TailoringMeasurement.objects.filter(user=user).first()
    if medida is None or not medida.is_current(now or timezone.now()):
        return None
    por_dimension = {}
    for campo, columna in DIMENSIONES.items():
        valor = getattr(medida, campo)
        if valor is None:
            continue
        por_dimension[columna] = _talla_para(columna, valor) or "out_of_guide"
    if not por_dimension:
        return None
    distintas = set(por_dimension.values())
    sugerida = distintas.pop() if len(distintas) == 1 and "out_of_guide" not in distintas else None
    return {
        "source": SOURCE,
        "by_dimension": por_dimension,
        "suggestion": sugerida,
        "measured_on": medida.captured_at.date().isoformat(),
    }
