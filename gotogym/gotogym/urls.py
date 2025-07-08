"""
URL configuration for gotogym project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import set_language
from django.shortcuts import redirect
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('accounts', lambda request: redirect('login', permanent=False)),
    path('setlang/', set_language, name='set_language'),
]

urlpatterns += i18n_patterns(
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('influencer/', include('influencer.urls')),
    # Password reset URLs
    path('accounts/password_reset/', auth_views.PasswordResetView.as_view(template_name='accounts/password_reset_form.html'), name='password_reset'),
    path('accounts/password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='accounts/password_reset_confirm.html'), name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'), name='password_reset_complete'),
    path('blog/', include('blog.urls', namespace='blog')),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('products/', include('products.urls', namespace='products')),
    path('configuracion-marca/', include('configuracion_marca.urls', namespace='configuracion_marca')),
    path('contabilidad/', include('contabilidad.urls', namespace='contabilidad')),
    path('tienda/', include('tienda.urls', namespace='tienda')),
    path('carrito/', include('carrito.urls', namespace='carrito')),
    path('crm/', include('crm.urls')),
    path('web/', include('web.urls', namespace='web')),
    path('metricas/', include('metricas.urls', namespace='metricas')),
    path('planes/', include('planes.urls')),
)

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
