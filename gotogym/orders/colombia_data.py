"""Departamentos y municipios de Colombia para el formulario de checkout.

Fuente: dataset publico basado en DIVIPOLA (marcovega/colombia-json), con
una correccion aplicada antes de guardarlo en `data/colombia.json`: Bogota
es su propio Distrito Capital, no un municipio de Cundinamarca, asi que se
separo como entrada propia ("Bogota D.C.").
"""
import json
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / 'data' / 'colombia.json'

with open(_DATA_PATH, encoding='utf-8') as _archivo:
    MUNICIPIOS_POR_DEPARTAMENTO = json.load(_archivo)

DEPARTAMENTOS = list(MUNICIPIOS_POR_DEPARTAMENTO.keys())


def municipios_de(departamento):
    return MUNICIPIOS_POR_DEPARTAMENTO.get(departamento, [])
