from rest_framework import serializers
from .models import HealthMetric


class HealthMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthMetric
        fields = ['id', 'user', 'source', 'metric_type', 'value', 'timestamp']
        read_only_fields = ['id']
