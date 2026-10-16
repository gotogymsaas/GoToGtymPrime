"""Texto de las paginas de politicas.

Cada politica es un diccionario con `title`, `summary` y `sections` (una lista
de `{'title', 'paragraphs'}`); `gotogym.views` las muestra con una sola
plantilla. Los plazos legales (retracto, reversion del pago, consultas y
reclamos de datos) salen de la Ley 1480 de 2011, el Decreto 587 de 2016 y la
Ley 1581 de 2012; los plazos propios de la marca (cambios, garantia) son
decisiones comerciales y se cambian aqui.
"""

RESPONSABLE = 'Friends N Gifts S.A.S.'
CORREO_SOPORTE = 'support@gotogym.store'
CORREO_PRIVACIDAD = 'privacy@gotogym.store'
ACTUALIZADO = 'Última actualización: octubre de 2026.'

PRIVACIDAD = {
    'title': 'Política de privacidad',
    'summary': 'Protegemos tus datos y los tratamos bajo principios de seguridad, transparencia y control por parte del titular.',
    'sections': [
        {'title': 'Lo que debes saber', 'paragraphs': [
            'GoToGym trata la información necesaria para gestionar tu cuenta, tus compras, '
            'la atención al cliente y las comunicaciones que hayas autorizado.',
            'No vendemos tus datos. Puedes solicitar acceso, corrección, actualización o '
            f'supresión escribiendo a {CORREO_PRIVACIDAD}.',
        ]},
        {'title': 'Más información', 'paragraphs': [
            'Qué datos recogemos, para qué los usamos, con quién los compartimos y cómo '
            'ejercer tus derechos está detallado en la política de tratamiento de datos personales.',
        ]},
    ],
}

CAMBIOS = {
    'title': 'Cambios',
    'summary': 'Cómo solicitar un cambio de talla o color y qué condiciones debe conservar la prenda.',
    'sections': [
        {'title': 'Cuándo puedes pedir un cambio', 'paragraphs': [
            'Puedes solicitar el cambio de talla o color dentro de los 15 días calendario siguientes '
            'a la entrega del pedido.',
            'El cambio está sujeto a la disponibilidad de la talla o el color que quieres. Si no '
            'tenemos existencias, te ofrecemos otra opción o la devolución del dinero.',
        ]},
        {'title': 'Condiciones de la prenda', 'paragraphs': [
            'La prenda debe estar sin usar, sin lavar, sin olores ni alteraciones, con sus etiquetas '
            'originales y en su empaque.',
        ]},
        {'title': 'Cómo hacerlo', 'paragraphs': [
            f'Escríbenos a {CORREO_SOPORTE} o desde la sección de contacto indicando tu número de pedido '
            '(GTG-AAAAMM-0000), la prenda y la talla o el color que prefieres. Te confirmamos cómo '
            'enviarla y te informamos el costo del transporte antes de coordinar el cambio.',
            'Si el cambio se debe a un error nuestro o a un defecto de la prenda, no tiene ningún costo para ti.',
        ]},
        {'title': 'Cambio y derecho de retracto', 'paragraphs': [
            'El cambio es un beneficio adicional de GoToGym y no sustituye tus derechos legales: '
            'si prefieres devolver la compra, consulta la política de devoluciones.',
        ]},
    ],
}

DEVOLUCIONES = {
    'title': 'Devoluciones',
    'summary': 'Cómo ejercer el derecho de retracto o devolver un producto con defecto o diferente al que compraste.',
    'sections': [
        {'title': 'Derecho de retracto', 'paragraphs': [
            'Como compras a distancia, puedes arrepentirte de la compra y devolverla sin dar explicaciones '
            'dentro de los 5 días hábiles siguientes a la entrega del pedido (artículo 47 de la Ley 1480 de 2011).',
            'La prenda debe llegar en las mismas condiciones en que la recibiste: sin usar, sin lavar, con sus '
            'etiquetas y en su empaque. Los costos de transporte de la devolución corren por tu cuenta.',
            'Tienes que avisarnos dentro de ese plazo escribiendo a '
            f'{CORREO_SOPORTE} con tu número de pedido.',
        ]},
        {'title': 'Producto con defecto o diferente al pedido', 'paragraphs': [
            'Si tu pedido llega con un defecto de fabricación, dañado o no corresponde a lo que compraste, '
            'avísanos lo antes posible con tu número de pedido y fotografías de la prenda y de su empaque. '
            'En estos casos no pagas el transporte de la devolución.',
            'Los defectos de fabricación se atienden bajo la garantía; consulta la política de garantía.',
        ]},
        {'title': 'Reembolso', 'paragraphs': [
            'Cuando recibimos la prenda y verificamos su estado, devolvemos el dinero por el mismo medio de '
            'pago que usaste, sin descuentos ni retenciones, y a más tardar dentro de los 30 días calendario '
            'siguientes a la fecha en que ejerciste el derecho. El tiempo en que el dinero aparece en tu '
            'cuenta depende de tu banco o del medio de pago.',
        ]},
        {'title': 'Reversión del pago', 'paragraphs': [
            'Si pagaste con tarjeta u otro instrumento electrónico y fuiste víctima de fraude, no solicitaste '
            'la compra, no recibiste el producto, o recibiste uno distinto o defectuoso, puedes pedir la '
            'reversión del pago (artículo 51 de la Ley 1480 de 2011 y Decreto 587 de 2016). Debes presentar '
            'la queja ante nosotros y avisar a la entidad emisora de tu instrumento de pago dentro de los '
            '5 días hábiles siguientes a que tuviste noticia de la operación.',
        ]},
    ],
}

GARANTIA = {
    'title': 'Garantía',
    'summary': 'La cobertura disponible ante posibles defectos de fabricación.',
    'sections': [
        {'title': 'Qué cubre', 'paragraphs': [
            'Las prendas GoToGym tienen garantía por defectos de fabricación durante los 3 meses siguientes '
            'a la entrega, bajo condiciones normales de uso y cuidado. Es una garantía de calidad, idoneidad '
            'y buen funcionamiento conforme a la Ley 1480 de 2011.',
        ]},
        {'title': 'Qué no cubre', 'paragraphs': [
            'No cubre el desgaste normal por uso, daños por mal uso, lavado o planchado distintos a los '
            'indicados en la etiqueta, cortes, quemaduras, manchas, ni alteraciones o arreglos hechos por '
            'terceros.',
        ]},
        {'title': 'Cómo hacerla efectiva', 'paragraphs': [
            f'Escríbenos a {CORREO_SOPORTE} con tu número de pedido, fotografías del defecto y una '
            'descripción breve. Revisamos tu caso y te indicamos cómo enviar la prenda, sin costo de '
            'transporte para ti cuando la garantía sea procedente.',
        ]},
        {'title': 'Qué solución recibes', 'paragraphs': [
            'Si la garantía procede, reparamos o cambiamos la prenda por otra igual o equivalente. '
            'Si el defecto no se puede resolver o vuelve a aparecer, puedes elegir entre un nuevo cambio '
            'o la devolución del dinero pagado.',
            'Esta garantía no limita los derechos que la ley colombiana te reconoce como consumidor. '
            'Si no estás de acuerdo con nuestra respuesta, puedes acudir a la Superintendencia de '
            'Industria y Comercio.',
        ]},
    ],
}

ENVIOS = {
    'title': 'Envíos',
    'summary': 'Cómo se calculan el tiempo y el costo de llevar tu pedido hasta ti.',
    'sections': [
        {'title': 'Cobertura y costo', 'paragraphs': [
            'Enviamos a todo el territorio colombiano. El costo depende de la ciudad de entrega: es una '
            'tarifa única para Bogotá, Medellín, Cali, Barranquilla y Bucaramanga, y otra para el resto '
            'del país. Siempre lo ves calculado en el checkout, antes de pagar, y se suma al total del pedido.',
        ]},
        {'title': 'Tiempos de entrega', 'paragraphs': [
            'Una vez confirmado el pago preparamos tu pedido. El tiempo estimado de entrega es de unos '
            '3 días hábiles en las ciudades principales y unos 6 días hábiles en el resto del país, contados '
            'desde la confirmación del pago. Son estimados: pueden variar por la transportadora, el clima '
            'o las condiciones de la zona.',
            'Te avisamos por correo electrónico cuando tu pedido sale y puedes consultar su estado en '
            '"Mis pedidos" dentro de tu cuenta.',
        ]},
        {'title': 'Dirección y recepción', 'paragraphs': [
            'Revisa que la dirección, la ciudad y el teléfono estén completos: una dirección errónea o '
            'un destinatario ausente pueden retrasar la entrega o generar costos de reenvío.',
            'Al recibir el paquete, revisa que el empaque esté en buen estado. Si notas un daño o una '
            f'diferencia con tu pedido, escríbenos cuanto antes a {CORREO_SOPORTE}.',
        ]},
    ],
}

PAGOS = {
    'title': 'Pagos',
    'summary': 'Cómo protegemos el proceso de pago y qué información nunca almacenamos.',
    'sections': [
        {'title': 'Cómo pagas', 'paragraphs': [
            'Los pagos se procesan a través de Mercado Pago. Cuando confirmas el pedido te llevamos a su '
            'plataforma segura, donde eliges entre los medios de pago que tengan habilitados (por ejemplo '
            'tarjetas de crédito y débito, PSE o pago en efectivo, según disponibilidad). Todos los precios '
            'están en pesos colombianos (COP).',
        ]},
        {'title': 'Seguridad', 'paragraphs': [
            'GoToGym no solicita, ve ni almacena los datos de tu tarjeta ni tus claves bancarias: se '
            'ingresan únicamente en Mercado Pago. Nosotros solo recibimos el estado del pago '
            '(aprobado, pendiente o rechazado).',
        ]},
        {'title': 'Confirmación y pagos pendientes', 'paragraphs': [
            'Tu pedido se confirma cuando el pago es aprobado. Mientras tanto queda "pendiente de pago" '
            'y las unidades no se reservan: si otra persona compra la última unidad antes de que se '
            'apruebe tu pago, te avisamos y te devolvemos el dinero.',
            'Si el pago no se completa dentro de las 48 horas siguientes a la creación del pedido, '
            'este se cancela automáticamente. Puedes volver a hacer tu compra cuando quieras.',
        ]},
        {'title': 'Pagos rechazados y reembolsos', 'paragraphs': [
            'Si tu pago es rechazado puedes intentarlo de nuevo con otro medio. Los reembolsos se hacen '
            'por el mismo medio de pago utilizado; consulta la política de devoluciones para los plazos.',
            f'Ante cualquier cobro que no reconozcas o duda sobre un pago, escríbenos a {CORREO_SOPORTE}.',
        ]},
        {'title': 'Quién te vende', 'paragraphs': [
            f'Las prendas de gotogym.store las vende {RESPONSABLE}, sociedad domiciliada en Bogotá D.C., '
            f'Colombia, titular de la marca GoToGym. Atención sobre tu compra: {CORREO_SOPORTE}.',
        ]},
    ],
}

TRATAMIENTO_DATOS = {
    'title': 'Tratamiento de datos personales',
    'summary': 'Las finalidades y principios aplicados a la información que compartes con GoToGym.',
    'sections': [
        {'title': 'Responsable del tratamiento', 'paragraphs': [
            f'{RESPONSABLE}, que opera la marca GoToGym, con domicilio en Bogotá D.C., Colombia, es el '
            'responsable del tratamiento de tus datos personales, de acuerdo con la Ley 1581 de 2012, '
            'el Decreto 1377 de 2013 (compilado en el Decreto 1074 de 2015) y las demás normas que los '
            f'complementan. Canal de atención: {CORREO_PRIVACIDAD}.',
        ]},
        {'title': 'Qué datos recogemos', 'paragraphs': [
            'Datos de identificación y contacto (nombre, correo electrónico, teléfono, edad si la indicas), '
            'datos de entrega (dirección, ciudad, departamento), datos de tus pedidos y pagos (sin datos '
            'de tarjeta), y datos de uso del sitio que no te identifican, como las páginas visitadas.',
            'Si participas en el programa de afiliados, también los datos necesarios para pagarte '
            'comisiones. No solicitamos datos sensibles.',
        ]},
        {'title': 'Para qué los usamos', 'paragraphs': [
            'Gestionar tu cuenta y tus pedidos, procesar pagos y envíos, atender solicitudes, cambios, '
            'garantías y devoluciones, cumplir obligaciones legales y contables, mejorar el sitio y, '
            'solo si lo autorizas, enviarte comunicaciones comerciales.',
        ]},
        {'title': 'Con quién los compartimos', 'paragraphs': [
            'Con proveedores que nos ayudan a operar y que tratan los datos solo para ese fin: la pasarela '
            'de pagos, las transportadoras, el servicio de correo electrónico y la infraestructura donde '
            'está alojado el sitio, que puede estar fuera de Colombia. También con autoridades cuando la '
            'ley lo exija. No vendemos tus datos.',
        ]},
        {'title': 'Tus derechos', 'paragraphs': [
            'Como titular puedes conocer, actualizar y rectificar tus datos; pedir prueba de la autorización; '
            'ser informado del uso que se les da; revocar la autorización y solicitar la supresión cuando '
            'no se respeten los principios y garantías legales; acceder gratuitamente a tus datos; y '
            'presentar quejas ante la Superintendencia de Industria y Comercio.',
        ]},
        {'title': 'Cómo ejercerlos', 'paragraphs': [
            f'Escribe a {CORREO_PRIVACIDAD} indicando tu nombre, el correo de tu cuenta y lo que solicitas. '
            'Atendemos las consultas en un máximo de 10 días hábiles y los reclamos en un máximo de '
            '15 días hábiles contados desde el día siguiente a su recibo; si necesitamos más tiempo, te '
            'avisamos el motivo y la nueva fecha, dentro de los límites que fija la ley.',
        ]},
        {'title': 'Seguridad y conservación', 'paragraphs': [
            'Aplicamos medidas técnicas y organizativas para proteger tus datos: conexión cifrada, control '
            'de acceso y contraseñas almacenadas de forma segura. Conservamos los datos mientras mantengas '
            'una relación con GoToGym y durante el tiempo que exijan las obligaciones legales.',
            'Actualizamos esta política cuando cambian nuestras prácticas o la ley; la versión vigente '
            f'es la publicada aquí. {ACTUALIZADO}',
        ]},
    ],
}

COOKIES = {
    'title': 'Política de cookies',
    'summary': 'Qué guarda GoToGym en tu navegador, para qué y cómo cambiar tu decisión cuando quieras.',
    'sections': [
        {'title': 'Qué son las cookies', 'paragraphs': [
            'Las cookies son pequeños archivos que un sitio guarda en tu navegador para recordar información '
            'entre una visita y otra. En GoToGym usamos solo las que necesita la tienda para funcionar y, si '
            'lo aceptas, una medición anónima del uso del sitio.',
            'No usamos cookies de publicidad ni de seguimiento entre sitios, no vendemos información sobre ti '
            'y el sitio no carga scripts, tipografías ni imágenes de terceros.',
        ]},
        {'title': 'Qué guardamos', 'paragraphs': [
            'Esta es la lista completa de lo que el sitio guarda en tu navegador.',
        ], 'table': {
            'headers': ['Nombre', 'Para qué sirve', 'Tipo', 'Duración'],
            'rows': [
                ['sessionid',
                 'Mantiene tu sesión, el carrito de compras y el código del afiliado si llegaste por su enlace.',
                 'Necesaria', '2 semanas'],
                ['csrftoken',
                 'Protege los formularios del sitio contra envíos falsificados.',
                 'Necesaria', 'Hasta 1 año'],
                ['django_language',
                 'Recuerda el idioma que elegiste. Solo se crea si lo cambias.',
                 'Necesaria', 'Hasta cerrar el navegador'],
                ['gtg_cookies',
                 'Guarda tu elección sobre las cookies para no preguntarte en cada visita.',
                 'Necesaria', '12 meses'],
                ['ARRAffinity, ARRAffinitySameSite',
                 'Las coloca el servicio de alojamiento (Azure App Service) para dirigir tus peticiones al mismo servidor.',
                 'Necesaria', 'Hasta cerrar el navegador'],
                ['gtg_atribucion',
                 'Almacenamiento de sesión del navegador. Solo si aceptas la analítica: recuerda que ya registramos de dónde llegaste en esta visita.',
                 'Analítica', 'Hasta cerrar la pestaña'],
            ],
        }},
        {'title': 'Medición anónima del uso del sitio', 'paragraphs': [
            'Solo si la aceptas en el banner, medimos qué páginas se visitan, qué botones se pulsan, qué se '
            'busca, qué productos se ven o se agregan al carrito y cuántos pedidos se crean. Cada visita lleva '
            'un identificador aleatorio sin relación con tu nombre ni tu correo, y no cruzamos estos datos con '
            'tu identidad. Los usamos únicamente para mejorar la tienda.',
            'Si no la aceptas, o tu navegador envía la señal "No rastrear" o Global Privacy Control, no medimos '
            'nada. Aceptar o rechazar la analítica no cambia en nada lo que puedes comprar ni cómo.',
        ]},
        {'title': 'Servicios de terceros', 'paragraphs': [
            'Cuando pagas, te llevamos a Mercado Pago, que es quien procesa el pago y puede guardar sus propias '
            'cookies en su plataforma, bajo su política. Los enlaces a nuestras redes sociales abren sus '
            'sitios, que tienen sus propias políticas.',
        ]},
        {'title': 'Cómo cambiar tu decisión', 'paragraphs': [
            'Puedes cambiarla cuando quieras con el botón de abajo. '
            'También puedes borrar o bloquear cookies desde la configuración de tu navegador; '
            'ten en cuenta que, si bloqueas las necesarias, no podrás iniciar sesión ni usar el carrito.',
        ], 'accion_cookies': 'Abrir preferencias de cookies'},
        {'title': 'Contacto y actualizaciones', 'paragraphs': [
            f'Si tienes preguntas sobre esta política, escribe a {CORREO_PRIVACIDAD}. Actualizamos esta política '
            f'cuando cambian las cookies que usamos; la versión vigente es la publicada aquí. {ACTUALIZADO}',
        ]},
    ],
}
