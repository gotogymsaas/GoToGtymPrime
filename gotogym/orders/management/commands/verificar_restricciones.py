"""Cuenta las filas que ya existen y violarian una `CheckConstraint` del esquema.

Se ejecuta contra la base real antes de aplicar una migracion que agrega
restricciones: PostgreSQL valida las filas existentes al crearlas y, si alguna
no cumple, la migracion falla a mitad del despliegue. Solo lee; no modifica
nada. Termina con codigo 1 si encuentra alguna.
"""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models


class Command(BaseCommand):
    help = 'Lista las filas existentes que incumplen alguna CheckConstraint de los modelos.'

    def handle(self, *args, **options):
        incumplimientos = 0
        revisadas = 0
        for modelo in apps.get_models():
            for restriccion in modelo._meta.constraints:
                if not isinstance(restriccion, models.CheckConstraint):
                    continue
                revisadas += 1
                filas = modelo._base_manager.exclude(restriccion.condition).count()
                if filas:
                    incumplimientos += filas
                    self.stdout.write(self.style.ERROR(
                        f'{modelo._meta.label}.{restriccion.name}: {filas} fila(s) no cumplen'
                    ))
        if incumplimientos:
            raise CommandError(f'{incumplimientos} fila(s) incumplen restricciones. Corrígelas antes de migrar.')
        self.stdout.write(self.style.SUCCESS(f'{revisadas} restricciones revisadas: todas las filas las cumplen.'))
