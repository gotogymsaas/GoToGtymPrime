# blog/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class Category(models.Model):
    name = models.CharField(_("Nombre"), max_length=50)
    slug = models.SlugField(_("Slug"), unique=True, blank=True)

    class Meta:
        verbose_name = _("Categoría")
        verbose_name_plural = _("Categorías")
        ordering = ("name",)

    def __str__(self):
        return self.name

    # genera slug automático una sola vez
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


class Post(models.Model):
    title     = models.CharField(_("Título"), max_length=200)
    slug      = models.SlugField(_("Slug"), unique=True, blank=True)
    author    = models.ForeignKey(User, verbose_name=_("Autor"), on_delete=models.CASCADE)
    category  = models.ForeignKey(Category, verbose_name=_("Categoría"), related_name="posts", on_delete=models.SET_NULL, null=True)
    excerpt   = models.TextField(_("Resumen"), blank=True)
    body      = models.TextField(_("Contenido"))
    featured  = models.ImageField(_("Imagen destacada"), upload_to="blog/images",null=False, blank=False, default="blog/images/placeholder.png",)
    published = models.DateTimeField(_("Publicado"), auto_now_add=True)
    updated   = models.DateTimeField(_("Actualizado"), auto_now=True)

    class Meta:
        ordering            = ("published",)
        verbose_name        = _("Entrada")
        verbose_name_plural = _("Entradas")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)
        super().save(*args, **kwargs)


    @property
    def reading_time(self) -> int:
        words = len(self.body.split())
        return max(1, round(words / 180))
