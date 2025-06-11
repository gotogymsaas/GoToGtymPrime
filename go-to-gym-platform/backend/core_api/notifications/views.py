from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model

from .models import Notification, DeviceToken
from .serializers import NotificationSerializer, DeviceTokenSerializer
from .tasks import send_push_notification, send_email_notification


class NotificationSendView(generics.CreateAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        user_id = request.data.get('user')
        title = request.data.get('title')
        body = request.data.get('body')
        channel = request.data.get('channel', 'push')
        template = request.data.get('template', 'generic_notification.html')

        user_model = get_user_model()
        try:
            user = user_model.objects.get(id=user_id)
        except user_model.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        notification = Notification.objects.create(user=user, title=title, body=body, type=request.data.get('type', 'generic'))
        if channel == 'push':
            tokens = DeviceToken.objects.filter(user=user)
            for device in tokens:
                send_push_notification.delay(device.token, title, body)
        elif channel == 'email':
            send_email_notification.delay(user.email, title, body, template)

        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)[:20]


class DeviceTokenView(generics.CreateAPIView):
    serializer_class = DeviceTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
