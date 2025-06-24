"""URL configuration for the influencer app."""
from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="influencer_dashboard"),
    path("promo/", views.promo_material, name="influencer_promo"),
    path("referral/", views.referral_page, name="influencer_referral_page"),
    path("payment/webhook/", views.payment_webhook, name="payment_webhook"),
]

# Optional API routes are added only if DRF is available
try:
    from rest_framework_simplejwt.views import TokenObtainPairView  # noqa: F401

    urlpatterns += [
        path("api/influencer/stats/", views.stats, name="api_influencer_stats"),
        path("api/influencer/withdraw/", views.withdraw, name="api_influencer_withdraw"),
    ]
except Exception:
    pass
