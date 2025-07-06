from django.db import models

class TemplateConfig(models.Model):
    TEMPLATE_CHOICES = [
        ('home', 'Home'),
    ]
    template_name = models.CharField(max_length=100, choices=TEMPLATE_CHOICES, unique=True)
    color = models.CharField(max_length=20, blank=True)
    image = models.ImageField(upload_to='web/', blank=True, null=True)
    font = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.template_name
