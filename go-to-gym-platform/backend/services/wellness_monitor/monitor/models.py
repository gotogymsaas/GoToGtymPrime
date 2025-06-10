from django.conf import settings
from django.db import models


class HealthMetric(models.Model):
    class Sources(models.TextChoices):
        GOOGLE_FIT = 'GoogleFit', 'Google Fit'
        APPLE_HEALTH = 'AppleHealth', 'Apple Health'
        SAMSUNG_HEALTH = 'SamsungHealth', 'Samsung Health'

    class MetricTypes(models.TextChoices):
        STEPS = 'steps', 'Steps'
        HEART_RATE = 'heart_rate', 'Heart Rate'
        SLEEP = 'sleep', 'Sleep'
        CALORIES = 'calories', 'Calories'
        OTHER = 'other', 'Other'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    source = models.CharField(max_length=32, choices=Sources.choices)
    metric_type = models.CharField(max_length=32, choices=MetricTypes.choices)
    value = models.FloatField()
    timestamp = models.DateTimeField()

    def __str__(self):
        return f"{self.user} {self.metric_type} {self.value}"
