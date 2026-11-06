"""Diagnostico de solo lectura del inicio de sesion unificado (OIDC).

Sirve para decidir si es seguro encenderlo y para comprobar, antes y despues,
que ninguna cuenta cambio. No escribe en la base de datos y nunca imprime
secretos, tokens, correos ni identificadores de personas: solo conteos, nombres
de verificacion y una huella con clave de los campos protegidos.

    python manage.py oidc_preflight                      # configuracion y migraciones
    python manage.py oidc_preflight --discovery          # ademas, consulta al proveedor
    python manage.py oidc_preflight --audit-preservation # huella de las cuentas
    python manage.py oidc_preflight --strict             # falla si algo bloqueante no esta

La huella de preservacion se toma antes de activar y se repite despues: si
coincide, las cuentas, contrasenas y permisos no cambiaron. Usa SECRET_KEY como
clave, asi que solo es comparable dentro del mismo entorno.
"""
import hashlib
import hmac
import json
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from gotogym_oidc import client, conf
from gotogym_oidc.models import ExternalIdentityLink

# Todo lo que decide quien es una persona, que puede hacer y con que entra. No
# incluye el ultimo acceso, que cambia con cada sesion.
CAMPOS_PROTEGIDOS = (
    'id', 'email', 'username', 'password', 'is_active', 'is_staff', 'is_superuser',
    'es_afiliado', 'accepted_terms', 'terms_accepted_at', 'terms_hash',
    'document_type', 'document_number', 'phone',
)
RUTA_CALLBACK = '/accounts/oidc/callback/'
# En producción Prime es otra aplicación Web en el MISMO tenant External ID.
# Estos son identificadores públicos, nunca valores secretos.
TENANT_ID = 'fe3cd367-0570-48e7-8a35-a777b62cc6f9'
ISSUER_ESPERADO = f'https://{TENANT_ID}.ciamlogin.com/{TENANT_ID}/v2.0'
CALLBACK_PRIME = 'https://shop.gotogym.store/accounts/oidc/callback/'
CLIENT_ID_COACH = '4fd1c894-78fa-496e-aaf2-5361da0dc430'


def _modo():
    if getattr(settings, 'OIDC_GLOBAL', False):
        return 'global'
    if getattr(settings, 'OIDC_CANARY', False):
        return 'canary'
    return 'apagado'


def _migraciones_pendientes():
    ejecutor = MigrationExecutor(connection)
    destinos = ejecutor.loader.graph.leaf_nodes('gotogym_oidc')
    return [f'{app}.{nombre}' for (app, nombre), _ in ejecutor.migration_plan(destinos)]


def _verificar(nombre, ok, detalle='', bloqueante=True):
    return {'check': nombre, 'ok': bool(ok), 'blocking': bloqueante, 'detail': detalle}


def verificaciones_de_configuracion():
    emisor = settings.GOTOGYM_OIDC.get('ISSUER') or ''
    secreto = settings.GOTOGYM_OIDC.get('CLIENT_SECRET') or ''
    retorno = settings.GOTOGYM_OIDC.get('REDIRECT_URI') or ''
    partes = urlsplit(retorno)
    pendientes = _migraciones_pendientes()
    modo = _modo()
    ids_canary = getattr(settings, 'OIDC_CANARY_OBJECT_IDS', frozenset())
    return [
        _verificar('issuer_configurado', emisor.startswith('https://'), 'OIDC_ISSUER debe ser https y exacto al discovery'),
        _verificar('client_id_configurado', bool(settings.GOTOGYM_OIDC.get('CLIENT_ID'))),
        # En la puesta en producción no basta un client_id presente: un
        # error copiando el cliente de Quantum Coach puede romper aud/redirect
        # y comprometer la separación de clientes.
        _verificar(
            'cliente_prime_independiente',
            not getattr(settings, 'PRODUCCION', False)
            or (bool(settings.GOTOGYM_OIDC.get('CLIENT_ID'))
                and settings.GOTOGYM_OIDC.get('CLIENT_ID') != CLIENT_ID_COACH),
            'Prime requiere su propia aplicacion Entra distinta de Quantum Coach',
        ),
        _verificar(
            'tenant_externo_correcto',
            not getattr(settings, 'PRODUCCION', False) or emisor == ISSUER_ESPERADO,
            'Comprobar el issuer exacto del tenant GoToGym Universal Identity',
        ),
        _verificar(
            'callback_prime_exacta',
            not getattr(settings, 'PRODUCCION', False) or retorno == CALLBACK_PRIME,
            'La callback de Prime debe ser la registrada en Entra para shop.gotogym.store',
        ),
        _verificar('client_secret_presente', bool(secreto)),
        # App Service sustituye las referencias a Key Vault antes de arrancar el
        # proceso; si llega el texto de la referencia, no se pudo resolver.
        _verificar('client_secret_resuelto', not secreto.startswith('@Microsoft.KeyVault'), 'La referencia a Key Vault no se resolvio'),
        _verificar(
            'redirect_uri_valida',
            partes.scheme == 'https' and partes.path == RUTA_CALLBACK and not partes.query,
            f'Debe ser https y terminar en {RUTA_CALLBACK}',
        ),
        _verificar('subject_claim_oid', settings.GOTOGYM_OIDC.get('SUBJECT_CLAIM') == 'oid', 'En Entra, sub cambia por aplicacion'),
        _verificar('migraciones_aplicadas', not pendientes, f'Pendientes: {", ".join(pendientes)}' if pendientes else ''),
        _verificar('canary_con_lista', modo != 'canary' or bool(ids_canary), 'Canary activo sin ningun oid permitido'),
        _verificar('secreto_exigido', conf.get('REQUIRE_CLIENT_SECRET'), bloqueante=False),
        _verificar('correo_verificado_exigido', conf.get('REQUIRE_EMAIL_VERIFIED_CLAIM'), 'Si se desactiva, el flujo de Entra debe verificar el correo', bloqueante=False),
        _verificar('alta_nueva_cerrada', not conf.get('ALLOW_AUTO_CREATE'), 'Informativo: con True se crean cuentas nuevas', bloqueante=False),
    ]


def verificar_discovery():
    try:
        metadatos = client.get_metadata()
    except (client.OIDCError, requests.RequestException, ValueError) as error:
        return [_verificar('discovery_accesible', False, f'{type(error).__name__}')]
    return [
        _verificar('discovery_accesible', True),
        _verificar(
            'issuer_coincide_con_el_discovery',
            metadatos.get('issuer') == settings.GOTOGYM_OIDC.get('ISSUER'),
            'El issuer del documento debe ser identico a OIDC_ISSUER',
        ),
        _verificar('cierre_de_sesion_disponible', bool(metadatos.get('end_session_endpoint')), bloqueante=False),
    ]


def huella_de_preservacion():
    modelo = get_user_model()
    disponibles = {campo.name for campo in modelo._meta.concrete_fields}
    campos = [campo for campo in CAMPOS_PROTEGIDOS if campo in disponibles]
    firma = hmac.new(settings.SECRET_KEY.encode(), digestmod=hashlib.sha256)
    cuentas = 0
    for fila in modelo.objects.order_by('pk').values(*campos).iterator(chunk_size=500):
        firma.update(json.dumps(fila, sort_keys=True, default=str, separators=(',', ':')).encode())
        firma.update(b'\n')
        cuentas += 1
    return {
        'accounts': cuentas,
        'protected_fields': campos,
        'keyed_fingerprint': firma.hexdigest(),
        'writes_performed': False,
    }


class Command(BaseCommand):
    help = 'Diagnostico de solo lectura del inicio de sesion unificado (OIDC).'

    def add_arguments(self, parser):
        parser.add_argument('--discovery', action='store_true', help='Consulta el documento de discovery del proveedor.')
        parser.add_argument('--audit-preservation', action='store_true', help='Huella con clave de los campos protegidos.')
        parser.add_argument('--strict', action='store_true', help='Termina con error si una verificacion bloqueante falla.')

    def handle(self, *args, **opciones):
        verificaciones = verificaciones_de_configuracion()
        if opciones['discovery']:
            verificaciones += verificar_discovery()
        listo = all(v['ok'] for v in verificaciones if v['blocking'])
        informe = {
            'mode': _modo(),
            'ready': listo,
            'checks': verificaciones,
            'identity_links': ExternalIdentityLink.objects.count(),
        }
        if opciones['audit_preservation']:
            informe['preservation'] = huella_de_preservacion()
        self.stdout.write(json.dumps(informe, sort_keys=True))
        if opciones['strict'] and not listo:
            raise CommandError('El inicio de sesion unificado no esta listo para encenderse.')
