"""Dias habiles de Colombia: de lunes a viernes, sin festivos.

Los plazos del programa (validacion de la comision, pago mensual) se cuentan
en dias habiles. Los festivos se calculan con la Ley 51 de 1983 (Ley
Emiliani): unos son fijos, otros se pasan al lunes siguiente, y los de
Semana Santa dependen de la fecha de Pascua. Asi no se necesita una tabla que
haya que actualizar cada ano ni una dependencia externa.
"""
from datetime import date, timedelta
from functools import cache

# (mes, dia) que no se mueven.
_FIJOS = [(1, 1), (5, 1), (7, 20), (8, 7), (12, 8), (12, 25)]
# (mes, dia) que, si no caen en lunes, pasan al lunes siguiente.
_EMILIANI = [(1, 6), (3, 19), (6, 29), (8, 15), (10, 12), (11, 1), (11, 11)]


def _pascua(anio):
    """Domingo de Pascua (algoritmo anonimo gregoriano)."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    mes, dia = divmod(h + ell - 7 * m + 114, 31)
    return date(anio, mes, dia + 1)


def _al_lunes(fecha):
    """El mismo dia si ya es lunes; si no, el lunes siguiente."""
    return fecha + timedelta(days=(7 - fecha.weekday()) % 7)


@cache
def festivos(anio):
    pascua = _pascua(anio)
    dias = {date(anio, mes, dia) for mes, dia in _FIJOS}
    dias |= {_al_lunes(date(anio, mes, dia)) for mes, dia in _EMILIANI}
    dias |= {pascua - timedelta(days=3), pascua - timedelta(days=2)}  # jueves y viernes santo
    # Ascension, Corpus Christi y Sagrado Corazon: caen en jueves o viernes y
    # se pasan al lunes siguiente.
    dias |= {_al_lunes(pascua + timedelta(days=n)) for n in (39, 60, 68)}
    return frozenset(dias)


def es_habil(fecha):
    return fecha.weekday() < 5 and fecha not in festivos(fecha.year)


def sumar_dias_habiles(fecha, cantidad):
    """La fecha que queda `cantidad` dias habiles despues de `fecha`. El dia
    de partida no cuenta: 5 dias habiles despues de un lunes es el lunes
    siguiente (si no hay festivos)."""
    actual = fecha
    restantes = cantidad
    while restantes > 0:
        actual += timedelta(days=1)
        if es_habil(actual):
            restantes -= 1
    return actual


def enesimo_dia_habil_del_mes(anio, mes, n):
    """El n-esimo dia habil de un mes (1 = el primero)."""
    actual = date(anio, mes, 1)
    contados = 0
    while True:
        if es_habil(actual):
            contados += 1
            if contados == n:
                return actual
        actual += timedelta(days=1)
