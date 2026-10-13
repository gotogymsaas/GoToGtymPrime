from django.contrib.syndication.views import Feed
from django.urls import reverse

from .models import Post


class JournalFeed(Feed):
    title = 'GoToGym Journal'
    description = (
        'Ciencia de materiales y ropa deportiva explicadas con sus fuentes: '
        'las últimas entradas del Journal de GoToGym.'
    )

    def link(self):
        return reverse('blog:post_list')

    def items(self):
        return Post.objects.filter(is_published=True).order_by('-published')[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.excerpt

    def item_author_name(self, item):
        return item.firma

    def item_categories(self, item):
        return [item.category.name] if item.category else []

    def item_pubdate(self, item):
        return item.published

    def item_updateddate(self, item):
        return item.updated
