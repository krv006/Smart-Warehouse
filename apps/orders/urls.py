from rest_framework.routers import DefaultRouter

from apps.orders.views import (OrderViewSet, ZakazViewSet,
                               ProductContractViewSet, BookingViewSet)

router = DefaultRouter()
# Zakaz/booking avval ro'yxatdan o'tishi kerak — URL conflict oldini olish uchun
router.register('zakaz',     ZakazViewSet,           basename='zakaz')
router.register('booking',   BookingViewSet,         basename='booking')
router.register('contracts', ProductContractViewSet, basename='product-contract')
router.register('',          OrderViewSet,           basename='order')

urlpatterns = router.urls
