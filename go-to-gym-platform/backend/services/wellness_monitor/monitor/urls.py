from django.urls import path
 hijjd8-codex/desarrollar-microservicio-wellness_monitor-en-django
from .views import UploadMetricView, MetricListView, index, MetricsPageView

from .views import UploadMetricView, MetricListView
 main

urlpatterns = [
    path('metrics/upload/', UploadMetricView.as_view(), name='upload-metric'),
    path('metrics/', MetricListView.as_view(), name='metric-list'),
 hijjd8-codex/desarrollar-microservicio-wellness_monitor-en-django
    path('', index, name='index'),
    path('metrics/page/', MetricsPageView.as_view(), name='metrics-page'),

 main
]
