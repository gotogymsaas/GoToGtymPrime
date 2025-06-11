from django.db import models
from django.utils.translation import gettext_lazy as _


class FrontendTranslation(models.Model):
    LANGUAGE_CHOICES = [
        ("es-CO", "Español (Colombia)"),
        ("pt-BR", "Português (Brasil)"),
        ("en-US", "English (US)"),
        ("en-GB", "English (UK)"),
    ]

    language_code = models.CharField(max_length=5, choices=LANGUAGE_CHOICES)
    namespace = models.CharField(max_length=100, default="common")
    key = models.CharField(max_length=200)
    text = models.TextField()

    class Meta:
        unique_together = ("language_code", "namespace", "key")
        verbose_name = _("Translation")
        verbose_name_plural = _("Translations")

    def __str__(self):
        return f"{self.language_code}:{self.namespace}:{self.key}"
