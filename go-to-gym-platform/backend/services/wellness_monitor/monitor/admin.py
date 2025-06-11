from django.contrib import admin

from .models import HealthMetric

@admin.register(HealthMetric)
class HealthMetricAdmin(admin.ModelAdmin):
    list_display = ("user", "metric_type", "value", "timestamp", "source")
    search_fields = ("user__email",)
    list_filter = ("metric_type", "source")
