from django.urls import path
from .views import NotificationSendView, NotificationListView, DeviceTokenView

urlpatterns = [
    path('notifications/send/', NotificationSendView.as_view(), name='send-notification'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('device-token/', DeviceTokenView.as_view(), name='device-token'),
]
