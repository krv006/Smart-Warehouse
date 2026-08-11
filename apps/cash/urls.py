from rest_framework.routers import DefaultRouter
from apps.cash.views import ExchangeRateViewSet, PaymentViewSet

router = DefaultRouter()
router.register('payments', PaymentViewSet, basename='payment')
router.register('exchange-rates', ExchangeRateViewSet, basename='exchange-rate')

urlpatterns = router.urls
