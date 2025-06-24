<<<<<<< HEAD
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf.urls.i18n import i18n_patterns

#  ← importa estas dos utilidades
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
]

urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('',  TemplateView.as_view(template_name='home.html'), name='home'),
    path('products/', include('products.urls', namespace='products')),
    path('metricas/',  include('metricas.urls')),
    path('gestion/',   include('gestion.urls')),
    path('',           include('users.urls')),
    path('blog/', include('blog.urls', namespace='blog')),
    path('dashboard/', include(('dashboard.urls', 'dashboard'), namespace='dashboard')),
    path('cart/',      include(('cart.urls', 'cart'),          namespace='cart')),
    path('tienda/',    include(('store.urls', 'store'),        namespace='store')),
    path('adminpanel/', include('adminpanel.urls')),
)

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )


# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('productos/', ProductListView.as_view(), name='list_product'),
# ]

=======
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf.urls.i18n import i18n_patterns

#  ← importa estas dos utilidades
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
]

urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('',  TemplateView.as_view(template_name='home.html'), name='home'),
    path('products/', include('products.urls', namespace='products')),
    path('metricas/',  include('metricas.urls')),
    path('gestion/',   include('gestion.urls')),
    path('',           include('users.urls')),
    path('blog/', include('blog.urls', namespace='blog')),
    path('api/', include('auth.urls')),
    path('dashboard/', include(('dashboard.urls', 'dashboard'), namespace='dashboard')),
    path('cart/',      include(('cart.urls', 'cart'),          namespace='cart')),
    path('tienda/',    include(('store.urls', 'store'),        namespace='store')),
    path('adminpanel/', include('adminpanel.urls')),
)

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )


# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('productos/', ProductListView.as_view(), name='list_product'),
# ]

>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
