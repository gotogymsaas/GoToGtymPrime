from django.db import models

class ColorMarca(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    codigo_hex = models.CharField(max_length=7, unique=True)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.codigo_hex})"

# Colores sugeridos por la paleta de la marca:
# 1. Negro Grafito      #101012
# 2. Verde Esmeralda    #1A9B76
# 3. Azul Zafiro        #17375C
# 4. Plata Premium      #E0E3E6
# 5. Dorado Fitness     #D4B46A
# 6. Cobalto Tecnológico #284F7E
# 7. Turquesa Grafeno   #0FBFB0
# 8. Púrpura Real       #69324F
# 9. Gris Carbono       #404045
# 10. Blanco Premium    #F8F9FA
