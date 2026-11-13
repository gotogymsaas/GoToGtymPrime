"""Contadores agregados de identidad: cuentan por dia y no pierden el valor."""
import time

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from . import telemetry

_LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@override_settings(CACHES=_LOCMEM)
class ContadoresDeIdentidadTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _valor(self, event, outcome):
        dia = int(time.time() // 86400)
        return cache.get(f'gotogym_oidc:metrics:{event}:{outcome}:{dia}')

    def test_cuenta_cada_evento(self):
        telemetry.record('authentication', 'success')
        telemetry.record('authentication', 'success')
        telemetry.record('authentication', 'failure')

        self.assertEqual(self._valor('authentication', 'success'), 2)
        self.assertEqual(self._valor('authentication', 'failure'), 1)

    def test_rechaza_etiquetas_desconocidas(self):
        with self.assertRaises(ValueError):
            telemetry.record('otro', 'success')

    def test_un_fallo_de_la_cache_no_rompe_la_autenticacion(self):
        from unittest.mock import patch

        with patch.object(cache, 'add', side_effect=OSError('cache caida')):
            telemetry.record('exchange', 'success')
