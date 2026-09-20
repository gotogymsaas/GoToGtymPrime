"""Validacion de origen de webhooks de Mercado Pago ("secret signature").

Implementa el esquema documentado por Mercado Pago: el header `x-signature`
trae `ts=<timestamp>,v1=<hash>`; el hash es un HMAC-SHA256 (en hexadecimal)
sobre un template `id:<data.id>;request-id:<x-request-id>;ts:<ts>;` firmado
con el secreto del webhook, omitiendo cualquier componente ausente.

No hay credenciales de sandbox reales para probar esto contra una
notificacion autentica de Mercado Pago. Antes de activar este endpoint en
produccion, confirmar el formato exacto contra la documentacion oficial
vigente en ese momento y una notificacion de prueba real.
"""
import hashlib
import hmac


def parse_x_signature(header_value):
    """Parsea 'ts=...,v1=...' del header x-signature.

    Devuelve `(ts, v1)`; cualquiera de los dos puede ser `None` si el header
    esta vacio o no trae ese componente.
    """
    partes = {}
    for fragmento in (header_value or '').split(','):
        if '=' not in fragmento:
            continue
        clave, _, valor = fragmento.partition('=')
        partes[clave.strip()] = valor.strip()
    return partes.get('ts'), partes.get('v1')


def build_signature_template(data_id, x_request_id, ts):
    """Arma el template documentado por Mercado Pago. Cualquier componente
    ausente se omite del template completo, tal como indica la
    documentacion oficial (no se firma un campo vacio)."""
    partes = []
    if data_id:
        partes.append(f'id:{data_id};')
    if x_request_id:
        partes.append(f'request-id:{x_request_id};')
    if ts:
        partes.append(f'ts:{ts};')
    return ''.join(partes)


def compute_signature(data_id, x_request_id, ts, secret):
    template = build_signature_template(data_id, x_request_id, ts)
    return hmac.new(secret.encode('utf-8'), template.encode('utf-8'), hashlib.sha256).hexdigest()


def verify_signature(request, secret):
    """Valida el header x-signature de una peticion contra `secret`.

    Devuelve False (nunca lanza) ante cualquier header ausente o mal
    formado: un webhook que no se puede validar se rechaza, no se asume
    valido.
    """
    if not secret:
        return False

    ts, v1 = parse_x_signature(request.headers.get('x-signature', ''))
    if not v1:
        return False

    data_id = request.GET.get('data.id') or request.GET.get('id', '')
    x_request_id = request.headers.get('x-request-id', '')

    esperado = compute_signature(data_id, x_request_id, ts, secret)
    return hmac.compare_digest(esperado, v1)
