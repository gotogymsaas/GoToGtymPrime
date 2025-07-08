from django.shortcuts import render

def planes_view(request):
    planes = [
        {
            'nombre': 'CHISPA ZERO',
            'precio': 'Free',
            'descripcion': 'El punto de partida para encender tu potencial',
            'beneficios': [
                'Descuentos Flash: Acceso a ofertas relámpago (hasta 15% en productos seleccionados).',
                'App Essential: Rutinas básicas de entrenamiento + seguimiento de puntos por compras.',
                'Newsletter Élite: Contenido exclusivo: tips nutricionales y tendencias fitness.',
                'Regalo de Cumpleaños: Cupón de 10% de descuento',
            ],
            'destacado': False,
        },
        {
            'nombre': 'BOOST ACTIVE',
            'precio': '$9.99/mes',
            'descripcion': 'Impulsa tu rendimiento sin límites',
            'beneficios': [
                'Envío Gratis: En compras superiores a $50.',
                'Descuento 20% Permanente: En toda la web (excepto lanzamientos).',
                'Early Access: 48 horas para comprar colecciones nuevas.',
                'Kit Supervivencia: Muestra gratis de bebida isotónica + calcetines técnicos al año.',
                'Puntos x2: En cada compra (canjeables por productos).',
            ],
            'destacado': False,
        },
        {
            'nombre': 'PEAK PRO',
            'precio': '$19.99/mes',
            'descripcion': 'Domina tu juego como un atleta de élite',
            'beneficios': [
                'Envío Express Gratis: Siempre, sin mínimo de compra.',
                'Descuento 30% Total: Incluye colecciones nuevas.',
                'Productos Secretos: Acceso a drops exclusivos y ediciones limitadas.',
                'Eventos VIP: Invitaciones a masterclass con atletas (online/presencial).',
                'Kit Pro: Protector solar + gel de recuperación muscular cada trimestre.',
                'Puntos x3: Redimibles hasta en outlet.',
            ],
            'destacado': True,
        },
        {
            'nombre': 'LEGEND INFINITY',
            'precio': '$29.99/mes',
            'descripcion': 'Vive la experiencia definitiva en rendimiento y lujo',
            'beneficios': [
                'Descuento 40% Ilimitado: Hasta en outlet + 1 invitado.',
                'Reembolso Fit: 15% de cashback anual en compras.',
                'Personal Shopper: Asesoría virtual mensual para tu kit deportivo.',
                'Viajes Élite: Descuentos en resorts deportivos y maratones internacionales.',
                'Experiencias Epic: Retiros fitness (yoga en montaña, surf camps) con 50% off.',
                'Kit Legend: Maletín con tecnología wearable (pulsera fitness) + mochila antibalas anual.',
            ],
            'destacado': True,
        },
    ]
    return render(request, 'planes/planes_list.html', {'planes': planes})
