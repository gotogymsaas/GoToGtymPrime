from rest_framework import serializers
from .models import Notification, DeviceToken


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'user', 'title', 'body', 'type', 'is_read', 'timestamp']
        read_only_fields = ['id', 'timestamp']


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['id', 'user', 'device_type', 'token', 'platform', 'created_at']
        read_only_fields = ['id', 'created_at']
