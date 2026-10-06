"""Paso previo a `migrate` para bases que vienen de cuando el programa se
llamaba "influencer": renombra tablas, migraciones y tipos de contenido, y no
hace nada si ya se hizo o si la base es nueva."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError, connections
from django.db.backends.sqlite3.base import DatabaseWrapper
from django.test import SimpleTestCase

from .adaptar_base import adaptar_base

ALIAS = 'simulada'


def _base_en_memoria():
    ajustes = {
        'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:', 'OPTIONS': {}, 'TIME_ZONE': None,
        'CONN_MAX_AGE': 0, 'CONN_HEALTH_CHECKS': False, 'AUTOCOMMIT': True, 'ATOMIC_REQUESTS': False,
        'USER': '', 'PASSWORD': '', 'HOST': '', 'PORT': '', 'TEST': {},
    }
    conexion = DatabaseWrapper(ajustes, alias=ALIAS)
    # `adaptar_base` abre su transaccion por alias: la conexion debe estar registrada.
    connections[ALIAS] = conexion
    return conexion


def _base_antigua(*, con_migraciones_nuevas=False, con_tabla_destino=False):
    conexion = _base_en_memoria()
    with conexion.cursor() as c:
        c.execute('CREATE TABLE django_migrations (id integer primary key, app varchar(255), name varchar(255))')
        c.execute('CREATE TABLE django_content_type (id integer primary key, app_label varchar(100), model varchar(100))')
        c.execute('CREATE TABLE influencer_influencerprofile (id integer primary key, referral_code varchar(36))')
        c.execute('CREATE TABLE influencer_commission (id integer primary key, influencer_id integer)')
        c.execute('CREATE TABLE orders_order (id integer primary key)')
        c.execute("INSERT INTO influencer_influencerprofile VALUES (1, 'MIMARCA')")
        c.execute("INSERT INTO django_migrations (app, name) VALUES ('influencer', '0001_initial'), "
                  "('influencer', '0002_x'), ('orders', '0006_coupon')")
        c.execute("INSERT INTO django_content_type (app_label, model) VALUES "
                  "('influencer', 'influencerprofile'), ('orders', 'order')")
        if con_migraciones_nuevas:
            c.execute("INSERT INTO django_migrations (app, name) VALUES ('afiliados', '0001_initial')")
        if con_tabla_destino:
            c.execute('CREATE TABLE afiliados_commission (id integer primary key)')
    return conexion


def _tablas(conexion):
    with conexion.cursor() as c:
        return set(conexion.introspection.table_names(c))


def _valores(conexion, sql):
    with conexion.cursor() as c:
        c.execute(sql)
        return [fila[0] for fila in c.fetchall()]


class AdaptarBaseTests(SimpleTestCase):
    databases = set()

    def tearDown(self):
        if ALIAS in connections.settings:
            connections[ALIAS].close()
        try:
            del connections[ALIAS]
        except KeyError:
            pass

    def test_renombra_tablas_migraciones_y_tipos_de_contenido_sin_perder_filas(self):
        conexion = _base_antigua()
        self.assertTrue(adaptar_base(conexion))

        tablas = _tablas(conexion)
        self.assertLessEqual({'afiliados_influencerprofile', 'afiliados_commission', 'orders_order'}, tablas)
        self.assertFalse({t for t in tablas if t.startswith('influencer_')})
        self.assertEqual(_valores(conexion, 'SELECT referral_code FROM afiliados_influencerprofile'), ['MIMARCA'])
        self.assertEqual(
            _valores(conexion, "SELECT name FROM django_migrations WHERE app = 'afiliados' ORDER BY name"),
            ['0001_initial', '0002_x'],
        )
        self.assertEqual(_valores(conexion, "SELECT COUNT(*) FROM django_migrations WHERE app = 'influencer'"), [0])
        self.assertEqual(_valores(conexion, "SELECT model FROM django_content_type WHERE app_label = 'afiliados'"),
                         ['influencerprofile'])
        # Las migraciones de otras apps no se tocan.
        self.assertEqual(_valores(conexion, "SELECT name FROM django_migrations WHERE app = 'orders'"), ['0006_coupon'])

    def test_es_idempotente(self):
        conexion = _base_antigua()
        self.assertTrue(adaptar_base(conexion))
        self.assertFalse(adaptar_base(conexion))
        self.assertEqual(_valores(conexion, 'SELECT COUNT(*) FROM afiliados_influencerprofile'), [1])

    def test_una_base_nueva_no_se_toca(self):
        conexion = _base_en_memoria()
        self.assertFalse(adaptar_base(conexion))  # ni siquiera existe django_migrations
        with conexion.cursor() as c:
            c.execute('CREATE TABLE django_migrations (id integer primary key, app varchar(255), name varchar(255))')
        self.assertFalse(adaptar_base(conexion))

    def test_una_base_a_medio_renombrar_se_rechaza_en_lugar_de_mezclarse(self):
        conexion = _base_antigua(con_migraciones_nuevas=True)
        with self.assertRaisesMessage(CommandError, 'a medio renombrar'):
            adaptar_base(conexion)
        self.assertIn('influencer_influencerprofile', _tablas(conexion))

    def test_si_la_tabla_destino_ya_existe_no_pisa_nada(self):
        conexion = _base_antigua(con_tabla_destino=True)
        with self.assertRaisesMessage(CommandError, 'influencer_commission'):
            adaptar_base(conexion)
        self.assertIn('influencer_commission', _tablas(conexion))
        self.assertEqual(_valores(conexion, "SELECT COUNT(*) FROM django_migrations WHERE app = 'influencer'"), [2])

    def test_un_fallo_a_mitad_deja_la_base_como_estaba(self):
        conexion = _base_antigua()
        with conexion.cursor() as c:
            # Sin la columna que el paso actualiza: falla despues de renombrar las tablas.
            c.execute('DROP TABLE django_content_type')
            c.execute('CREATE TABLE django_content_type (id integer primary key)')
        with self.assertRaises(OperationalError):
            adaptar_base(conexion)
        self.assertIn('influencer_influencerprofile', _tablas(conexion))
        self.assertEqual(_valores(conexion, "SELECT COUNT(*) FROM django_migrations WHERE app = 'influencer'"), [2])


class ComandoMigrateTests(SimpleTestCase):
    databases = set()

    def test_migrate_adapta_la_base_antes_de_migrar(self):
        with patch('afiliados.management.commands.migrate.adaptar_base', return_value=False) as adaptar:
            with patch('django.core.management.commands.migrate.Command.handle', return_value='') as migrar:
                call_command('migrate', verbosity=0, stdout=StringIO())
        adaptar.assert_called_once()
        migrar.assert_called_once()

    def test_plan_y_check_no_modifican_la_base(self):
        for opcion in ('--plan', '--check'):
            with self.subTest(opcion=opcion):
                with patch('afiliados.management.commands.migrate.adaptar_base') as adaptar:
                    with patch('django.core.management.commands.migrate.Command.handle', return_value=''):
                        call_command('migrate', opcion, verbosity=0, stdout=StringIO())
                adaptar.assert_not_called()
