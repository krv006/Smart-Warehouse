from rest_framework.routers import DefaultRouter

from apps.common.views import PendingChangeViewSet

router = DefaultRouter()
router.register('pending-changes', PendingChangeViewSet, basename='pending-change')

urlpatterns = router.urls
