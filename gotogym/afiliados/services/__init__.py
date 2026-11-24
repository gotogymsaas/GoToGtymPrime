"""Logica de negocio del programa de afiliados: aprobacion, comisiones,
pagos y salida del programa.

Cada modulo cubre una etapa del ciclo de vida; este paquete reexporta los
nombres publicos para que el resto del codigo siga importando desde
`afiliados.services`. Las pruebas que sustituyen una funcion apuntan al modulo
donde se usa (por ejemplo `afiliados.services.avisos.enviar_correo`).

- `afiliacion`: aprobacion, rechazo, baja con preaviso, terminos y actividad.
- `comisiones`: registro, validacion, confirmacion y anulacion de comisiones.
- `pagos`: solicitudes de pago, su resolucion e historial.
- `avisos`: correos a los afiliados.
"""
from .afiliacion import (
    DIAS_DE_PREAVISO,
    aceptar_terminos_vigentes,
    afiliado_operativo,
    afiliados_inactivos,
    aplicar_bajas_vencidas,
    approve_afiliado,
    cancelar_baja,
    deactivate_afiliado,
    necesita_reaceptar_terminos,
    reject_afiliado,
    solicitar_baja,
    ultima_actividad,
)
from .avisos import (
    avisar_afiliados,
    avisar_cambio_de_tasa,
    notify_commission_paid,
    perfiles_activos,
)
from .comisiones import (
    DIAS_DE_VALIDACION,
    ESTADOS_DE_PEDIDO_NO_VALIDOS,
    REEMBOLSOS_QUE_ANULAN,
    anular_comision,
    confirmar_comisiones_vencidas,
    extender_validacion,
    fin_de_validacion,
    get_commission_rate,
    liberar_revision,
    pedido_reembolsado,
    pedidos_validos,
    razon_de_revision,
    recompute_profile_totals,
    register_order_commission,
    revert_order_commission,
    saldo_para_pago,
    schedule_order_commission_validation,
)
from .pagos import (
    DIAS_HABILES_PARA_PAGAR,
    MontoMinimoError,
    anio_pedido,
    fecha_limite_de_la_solicitud,
    fecha_limite_de_pago,
    historial_de_pagos,
    mes_pedido,
    pagos_por_mes,
    request_withdrawal,
    resolve_withdrawal,
    total_pagado_en_anio,
    totales_pagados_por_anio,
)

__all__ = [
    'DIAS_DE_PREAVISO',
    'DIAS_DE_VALIDACION',
    'DIAS_HABILES_PARA_PAGAR',
    'ESTADOS_DE_PEDIDO_NO_VALIDOS',
    'REEMBOLSOS_QUE_ANULAN',
    'MontoMinimoError',
    'aceptar_terminos_vigentes',
    'afiliado_operativo',
    'afiliados_inactivos',
    'anio_pedido',
    'anular_comision',
    'aplicar_bajas_vencidas',
    'approve_afiliado',
    'avisar_afiliados',
    'avisar_cambio_de_tasa',
    'cancelar_baja',
    'confirmar_comisiones_vencidas',
    'deactivate_afiliado',
    'extender_validacion',
    'fecha_limite_de_la_solicitud',
    'fecha_limite_de_pago',
    'fin_de_validacion',
    'get_commission_rate',
    'historial_de_pagos',
    'liberar_revision',
    'mes_pedido',
    'necesita_reaceptar_terminos',
    'notify_commission_paid',
    'pagos_por_mes',
    'pedido_reembolsado',
    'pedidos_validos',
    'perfiles_activos',
    'razon_de_revision',
    'recompute_profile_totals',
    'register_order_commission',
    'reject_afiliado',
    'request_withdrawal',
    'resolve_withdrawal',
    'revert_order_commission',
    'saldo_para_pago',
    'schedule_order_commission_validation',
    'solicitar_baja',
    'total_pagado_en_anio',
    'totales_pagados_por_anio',
    'ultima_actividad',
]
