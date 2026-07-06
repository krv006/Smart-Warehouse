from rest_framework.routers import DefaultRouter

from apps.orders.views import (OrderViewSet, ZakazViewSet,
                               ProductContractViewSet)

router = DefaultRouter()
# Zakaz avval ro'yxatdan o'tishi kerak — URL conflict oldini olish uchun
router.register('zakaz',     ZakazViewSet,           basename='zakaz')
router.register('contracts', ProductContractViewSet, basename='product-contract')
router.register('',          OrderViewSet,           basename='order')

urlpatterns = router.urls
