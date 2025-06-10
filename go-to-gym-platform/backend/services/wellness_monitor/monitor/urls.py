from django.urls import path
from .views import UploadMetricView, MetricListView

urlpatterns = [
    path('metrics/upload/', UploadMetricView.as_view(), name='upload-metric'),
    path('metrics/', MetricListView.as_view(), name='metric-list'),
]
