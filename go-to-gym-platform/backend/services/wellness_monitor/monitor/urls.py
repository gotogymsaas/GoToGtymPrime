from django.urls import path
from .views import UploadMetricView, MetricListView, index, MetricsPageView

urlpatterns = [
    path('metrics/upload/', UploadMetricView.as_view(), name='upload-metric'),
    path('metrics/', MetricListView.as_view(), name='metric-list'),
    path('', index, name='index'),
    path('metrics/page/', MetricsPageView.as_view(), name='metrics-page'),
]
