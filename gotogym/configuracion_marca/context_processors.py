from .models import ColorMarca

def color_navbar(request):
    color = "#1274A5"  # fallback color navbar
    color_body = '#F8F9FA'  # fallback color body
    try:
        # Navbar: décimo color (índice 8)
        color_obj_navbar = ColorMarca.objects.order_by('id')[8]
        color = color_obj_navbar.codigo_hex
    except (ColorMarca.DoesNotExist, IndexError, AttributeError):
        pass
    try:
        # Body: quinto color (índice 4)
        color_obj_body = ColorMarca.objects.order_by('id')[4]
        color_body = color_obj_body.codigo_hex
    except (ColorMarca.DoesNotExist, IndexError, AttributeError):
        pass
    return {'color_navbar': color, 'color_body': color_body}
