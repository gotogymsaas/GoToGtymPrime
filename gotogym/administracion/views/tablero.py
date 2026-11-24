"""Tablero de ventas, analitica y exportacion de pedidos del panel."""
import csv
from datetime import datetime, timedelta

from afiliados.models import (
    Commission,
    CommissionStatus,
    EstadoAfiliado,
    PerfilAfiliado,
    WithdrawalRequest,
    WithdrawalStatus,
)
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from inventory.models import Inventory
from orders.models import Coupon
from products.models import (
    Product,
    ProductCategory,
)

from .. import metrics
from ..forms import SalesGoalForm
from ..models import PanelSettings
from ..permissions import (
    require_perms,
    staff_required,
)


def _rango_de_fechas(request, dias_por_defecto=30, maximo=366):
    """Rango `desde`/`hasta` del filtro, acotado para no calcular series de
    varios anos por un parametro mal escrito."""
    hoy = timezone.localdate()
    hasta = _parse_fecha(request.GET.get("hasta", ""), hoy)
    desde = _parse_fecha(request.GET.get("desde", ""), hoy - timedelta(days=dias_por_defecto))
    if desde > hasta:
        desde, hasta = hasta, desde
    if (hasta - desde).days >= maximo:
        desde = hasta - timedelta(days=maximo - 1)
    return desde, hasta


@staff_required
def dashboard(request):
    """Panel unico de gestion.

    Las cifras de ventas salen de `administracion.metrics`, donde estan
    escritas sus definiciones: una venta valida excluye pedidos cancelados o
    devueltos, el ingreso es neto de reembolsos, y cada indicador se compara
    con el periodo anterior de igual duracion."""
    User = get_user_model()
    panel_settings = PanelSettings.load()
    threshold = panel_settings.low_stock_threshold

    desde, hasta = _rango_de_fechas(request)
    desde_anterior, hasta_anterior = metrics.periodo_anterior(desde, hasta)

    resumen = metrics.resumen_ventas(desde, hasta)
    anterior = metrics.resumen_ventas(desde_anterior, hasta_anterior)
    comparacion = {
        clave: metrics.variacion(resumen[clave], anterior[clave])
        for clave in ("pedidos", "neto", "ticket_promedio", "unidades")
    }
    canales = metrics.canales_de_venta(desde, hasta)

    comisiones = Commission.objects.filter(
        created_at__date__gte=desde, created_at__date__lte=hasta,
    ).aggregate(
        pendiente=Sum("amount", filter=Q(status=CommissionStatus.PENDING)),
        aprobada=Sum("amount", filter=Q(status=CommissionStatus.APPROVED)),
        pagada=Sum("amount", filter=Q(status=CommissionStatus.PAID)),
    )
    comisionado = sum((comisiones[k] or 0) for k in ("pendiente", "aprobada", "pagada"))
    ventas_afiliados = next((c["ventas"] for c in canales if c["canal"] == "Con cupón de afiliado"), 0)

    # Reemplaza a "Productos recientes"/"Usuarios recientes" (duplicaban lo
    # que ya hacen /productos/ y /usuarios/ con busqueda real, sin ayudar a
    # decidir nada): esto si es accionable, apunta directo a que producto
    # reabastecer.
    bajo_stock = (
        Inventory.objects
        .filter(quantity_available__lte=threshold)
        .select_related("variant__product")
        .order_by("quantity_available")[:10]
    )

    context = {
        "desde": desde,
        "hasta": hasta,
        "desde_anterior": desde_anterior,
        "hasta_anterior": hasta_anterior,
        "resumen": resumen,
        "anterior": anterior,
        "comparacion": comparacion,
        "anuladas": metrics.ventas_anuladas(desde, hasta),
        "serie_diaria": metrics.serie_diaria(desde, hasta),
        "productos_top": metrics.top_productos(desde, hasta),
        "categorias": metrics.ventas_por_categoria(desde, hasta),
        "canales": canales,
        "comisiones": comisiones,
        "comision_sobre_ventas_afiliados": (
            round(float(comisionado) / float(ventas_afiliados) * 100, 1) if ventas_afiliados else None
        ),
        "meta_mes": metrics.meta_del_mes(panel_settings.monthly_sales_goal),
        "sales_goal_form": SalesGoalForm(instance=panel_settings),
        "bajo_stock": bajo_stock,
        "low_stock_threshold": threshold,
        "product_count": Product.objects.count(),
        "user_count": User.objects.count(),
        "afiliado_count": PerfilAfiliado.objects.filter(
            is_active=True, status=EstadoAfiliado.APPROVED,
        ).count(),
        "pending_afiliado_count": PerfilAfiliado.objects.filter(status=EstadoAfiliado.PENDING).count(),
        "pending_withdrawal_count": WithdrawalRequest.objects.filter(status=WithdrawalStatus.PENDING).count(),
        "category_count": ProductCategory.objects.count(),
        "low_stock_count": Inventory.objects.filter(
            quantity_available__gt=0, quantity_available__lte=threshold,
        ).count(),
        "out_of_stock_count": Inventory.objects.filter(quantity_available=0).count(),
        "active_coupon_count": Coupon.objects.filter(is_active=True).count(),
    }
    return render(request, "administracion/dashboard.html", context)


@staff_required
def analytics(request):
    """Comportamiento de la tienda: embudo, canales, busquedas, clientes,
    cupones, operacion e inventario. Complementa al dashboard (que responde
    "cuanto vendimos") con "por que" y "que hacer"."""
    desde, hasta = _rango_de_fechas(request)
    context = {
        "desde": desde,
        "hasta": hasta,
        "embudo": metrics.embudo(desde, hasta),
        "canales_trafico": metrics.canales_de_trafico(desde, hasta),
        "busquedas": metrics.busquedas(desde, hasta),
        "clientes": metrics.clientes(desde, hasta),
        "canales_venta": metrics.canales_de_venta(desde, hasta),
        "cupones": metrics.rendimiento_de_cupones(desde, hasta),
        "pipeline": metrics.pipeline_de_pedidos(desde, hasta),
        "inventario": metrics.salud_de_inventario(),
        "resumen": metrics.resumen_ventas(desde, hasta),
    }
    return render(request, "administracion/analytics.html", context)


def _celda_segura(valor):
    """Evita que una hoja de calculo interprete un texto como formula."""
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@"):
        return "'" + valor
    return valor


@require_perms("orders.view_order")
def export_orders_csv(request):
    """Pedidos del rango en CSV, para analizarlos fuera del panel. No incluye
    correo ni telefono: el cliente va como identificador interno."""
    desde, hasta = _rango_de_fechas(request)
    respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="pedidos_{desde}_{hasta}.csv"'
    respuesta.write("﻿")  # BOM: Excel abre bien los acentos
    escritor = csv.DictWriter(respuesta, fieldnames=metrics.COLUMNAS_EXPORTACION)
    escritor.writeheader()
    for fila in metrics.filas_exportacion(desde, hasta):
        escritor.writerow({clave: _celda_segura(valor) for clave, valor in fila.items()})
    return respuesta


def _parse_fecha(valor, por_defecto):
    if not valor:
        return por_defecto
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        return por_defecto
