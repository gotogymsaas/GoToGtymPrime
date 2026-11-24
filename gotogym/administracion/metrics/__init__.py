"""Metricas de negocio del panel: definiciones, no pantallas.

Cada funcion devuelve datos planos para que las vistas y las pruebas
dependan de la *definicion* de la metrica y no de como se dibuja.

Definiciones que importan (y por que estan escritas aqui)
---------------------------------------------------------

**Venta valida** = pago aprobado y pedido que no esta cancelado ni devuelto.
`payment_status` no cambia cuando un pedido se cancela, se devuelve o se
reembolsa (lo controla solo el proveedor de pago), asi que filtrar solo por
"pago aprobado" cuenta como ingreso dinero que en realidad ya se reintegro o
se debe reintegrar. Esos pedidos se muestran aparte como *ventas anuladas*,
con lo que falta por devolver, que es lo accionable.

**Ingreso neto** = total cobrado de las ventas validas menos los reembolsos
aprobados sobre ellas (devoluciones parciales).

**Ticket promedio** = total cobrado / pedidos validos (incluye envio, porque
es lo que paga el cliente en cada compra).

**Periodo anterior** = el mismo numero de dias inmediatamente antes del rango
elegido. Un numero sin termino de comparacion no dice si el negocio va bien.

**Fecha de una venta** = la de creacion del pedido. No hay fecha de
aprobacion del pago guardada en el pedido; con pagos de aprobacion diferida
una venta puede caer en un dia anterior al de su cobro.

**Tarjetas de regalo** = su compra no es una venta de mercancia: se cuenta
cuando se canjea, en el pedido que la usa (como la factura). Por eso los
pedidos de compra de tarjetas quedan fuera de todas las metricas de ventas y
se ven en el panel de tarjetas. En un pedido canjeado, `total` es lo cobrado
por el proveedor; lo pagado con la tarjeta va en `gift_card_total`.

**Embudo** = sesiones (visitantes estables, ver `analitica.services`) que
alcanzaron cada etapa, donde cada etapa exige haber pasado la anterior. Mide
solo a quien acepta ser medido: quedan fuera las personas con Do Not Track
y las que usan bloqueadores, asi que las cifras absolutas son un piso y lo
util son las proporciones entre etapas.

Las funciones viven en los modulos de este paquete y se reexportan aqui:
`administracion.metrics.<nombre>` sigue siendo la direccion publica.
"""

from ._base import (
    CERO,
    VENTA_ANULADA,
    VENTA_VALIDA,
    _dec,
    _pct,
    _pedidos,
    periodo_anterior,
    variacion,
)
from .clientes import (
    canales_de_venta,
    clientes,
    rendimiento_de_cupones,
)
from .embudo import (
    ANCHO_MOVIL,
    ETAPAS,
    _canal_de,
    _dispositivo_por_sesion,
    _etapas,
    _filas_embudo,
    _sesiones,
    busquedas,
    canales_de_trafico,
    embudo,
)
from .exportacion import (
    COLUMNAS_EXPORTACION,
    filas_exportacion,
)
from .operacion import (
    DIAS_COBERTURA_CRITICA,
    DIAS_ROTACION,
    pipeline_de_pedidos,
    salud_de_inventario,
)
from .ventas import (
    meta_del_mes,
    resumen_ventas,
    serie_diaria,
    top_productos,
    ventas_anuladas,
    ventas_por_categoria,
)

__all__ = [
    "ANCHO_MOVIL",
    "CERO",
    "COLUMNAS_EXPORTACION",
    "DIAS_COBERTURA_CRITICA",
    "DIAS_ROTACION",
    "ETAPAS",
    "VENTA_ANULADA",
    "VENTA_VALIDA",
    "_canal_de",
    "_dec",
    "_dispositivo_por_sesion",
    "_etapas",
    "_filas_embudo",
    "_pct",
    "_pedidos",
    "_sesiones",
    "busquedas",
    "canales_de_trafico",
    "canales_de_venta",
    "clientes",
    "embudo",
    "filas_exportacion",
    "meta_del_mes",
    "periodo_anterior",
    "pipeline_de_pedidos",
    "rendimiento_de_cupones",
    "resumen_ventas",
    "salud_de_inventario",
    "serie_diaria",
    "top_productos",
    "variacion",
    "ventas_anuladas",
    "ventas_por_categoria",
]
