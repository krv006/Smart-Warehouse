from rest_framework.routers import DefaultRouter
from apps.cash.views import PaymentViewSet

router = DefaultRouter()
router.register('payments', PaymentViewSet, basename='payment')

urlpatterns = router.urls
