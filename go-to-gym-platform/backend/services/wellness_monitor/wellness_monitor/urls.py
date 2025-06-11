from django.contrib import admin
from django.urls import path, include
 hijjd8-codex/desarrollar-microservicio-wellness_monitor-en-django

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
 main

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('monitor.urls')),
 hijjd8-codex/desarrollar-microservicio-wellness_monitor-en-django

    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
main
]
