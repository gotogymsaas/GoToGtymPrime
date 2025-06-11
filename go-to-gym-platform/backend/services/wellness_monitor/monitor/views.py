from rest_framework import generics, permissions
 hijjd8-codex/desarrollar-microservicio-wellness_monitor-en-django

from django.shortcuts import render
from django.views.generic import TemplateView

from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
 main
from datetime import datetime

from .models import HealthMetric
from .serializers import HealthMetricSerializer
from .services import get_metrics


class UploadMetricView(generics.CreateAPIView):
    queryset = HealthMetric.objects.all()
    serializer_class = HealthMetricSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        if serializer.validated_data['user'].id != self.request.user.id:
            raise permissions.PermissionDenied('Cannot upload metrics for another user')
        serializer.save()


class MetricListView(generics.ListAPIView):
    serializer_class = HealthMetricSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        metric_type = self.request.query_params.get('metric_type')
        start = self.request.query_params.get('start')
        end = self.request.query_params.get('end')
        start_dt = None
        end_dt = None
        if start:
            start_dt = datetime.fromisoformat(start)
        if end:
            end_dt = datetime.fromisoformat(end)
        return get_metrics(self.request.user, metric_type=metric_type, start=start_dt, end=end_dt)
 hijjd8-codex/desarrollar-microservicio-wellness_monitor-en-django


def index(request):
    """Simple page to confirm the service is running."""
    return render(request, 'monitor/index.html')


class MetricsPageView(TemplateView):
    template_name = 'monitor/metrics_list.html'
    permission_classes = [permissions.IsAuthenticated]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['metrics'] = get_metrics(self.request.user)
        return context

 main
