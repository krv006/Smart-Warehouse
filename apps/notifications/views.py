from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer


@extend_schema_view(
    list=extend_schema(summary="Mening bildirishnomalarim", tags=["Notifications"]),
    retrieve=extend_schema(summary="Bildirishnoma", tags=["Notifications"]),
)
class NotificationViewSet(ReadOnlyModelViewSet):
    serializer_class   = NotificationSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields   = ('is_read',)

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @extend_schema(summary="O'qilgan deb belgilash", tags=["Notifications"])
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)

    @extend_schema(summary="Hammasini o'qilgan deb belgilash", tags=["Notifications"])
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'status': 'ok'})
