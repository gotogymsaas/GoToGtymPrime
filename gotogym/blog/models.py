from django.contrib.auth import get_user_model
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    author = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='posts')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='posts')
    excerpt = models.TextField(blank=True)
    content = models.TextField()
    references = models.TextField(
        blank=True,
        help_text=(
            'Una referencia por linea, con el formato "Texto de la referencia | URL". '
            'En el contenido se citan como [1], [2]... segun el orden de esta lista.'
        ),
    )
    featured = models.ImageField(upload_to='blog/featured/', blank=True, null=True)
    published = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    reading_time = models.PositiveIntegerField(default=3)
    is_published = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def reference_items(self):
        """Referencias ya separadas en texto y enlace, en el orden de la lista."""
        items = []
        for line in self.references.splitlines():
            line = line.strip()
            if not line:
                continue
            text, _, url = line.partition('|')
            items.append({'text': text.strip(), 'url': url.strip()})
        return items
