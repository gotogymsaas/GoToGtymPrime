from datetime import datetime
from .models import HealthMetric


def get_metrics(user, metric_type=None, start: datetime | None = None, end: datetime | None = None):
    """Return metrics for a user filtered by type and date range."""
    qs = HealthMetric.objects.filter(user=user)
    if metric_type:
        qs = qs.filter(metric_type=metric_type)
    if start:
        qs = qs.filter(timestamp__gte=start)
    if end:
        qs = qs.filter(timestamp__lte=end)
    return qs.order_by('timestamp')
