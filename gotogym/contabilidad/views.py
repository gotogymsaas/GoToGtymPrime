from django.shortcuts import render, redirect
from .alegra import AlegraAPI
from django.conf import settings

def clientes(request):
    api = AlegraAPI(
        email=getattr(settings, 'ALEGRA_EMAIL', None),
        api_token=getattr(settings, 'ALEGRA_API_TOKEN', None)
    )
    clientes = []
    error = None
    filtro = request.GET.get('filtro', '').lower()
    try:
        clientes = api.get_clients()
        if filtro:
            clientes = [c for c in clientes if filtro in c.get('name', '').lower() or filtro in c.get('email', '').lower()]
    except Exception as e:
        error = str(e)
    return render(request, 'contabilidad/clientes.html', {
        'clientes': clientes,
        'error': error,
        'filtro': filtro
    })

def facturas_cliente(request, cliente_id):
    api = AlegraAPI(
        email=getattr(settings, 'ALEGRA_EMAIL', None),
        api_token=getattr(settings, 'ALEGRA_API_TOKEN', None)
    )
    cliente = None
    facturas = []
    error = None
    filtro_factura = request.GET.get('filtro_factura', '').lower()
    try:
        clientes = api.get_clients()
        cliente = next((c for c in clientes if str(c['id']) == str(cliente_id)), None)
        facturas = [f for f in api.get_invoices() if f.get('client', {}).get('id') == str(cliente_id)]
        if filtro_factura:
            facturas = [f for f in facturas if filtro_factura in str(f.get('number', '')).lower() or filtro_factura in str(f.get('status', '')).lower()]
    except Exception as e:
        error = str(e)
    return render(request, 'contabilidad/facturas_cliente.html', {
        'cliente': cliente,
        'facturas': facturas,
        'error': error
    })
