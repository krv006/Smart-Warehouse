from rest_framework.routers import DefaultRouter
from apps.orders.views import OrderViewSet

router = DefaultRouter()
router.register('', OrderViewSet, basename='order')
urlpatterns = router.urls
