from rest_framework.serializers import ModelSerializer

from apps.notifications.models import Notification


class NotificationSerializer(ModelSerializer):
    class Meta:
        model  = Notification
        fields = ('id', 'title', 'message', 'is_read', 'created_at')
        read_only_fields = ('id', 'title', 'message', 'created_at')
