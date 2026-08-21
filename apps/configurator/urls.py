from rest_framework.routers import DefaultRouter

from apps.configurator.views import ServerConfigurationViewSet

router = DefaultRouter()
router.register('', ServerConfigurationViewSet, basename='configuration')

urlpatterns = router.urls
