from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.views import ProductViewSet, StockViewSet, SaleViewSet, reports

router = DefaultRouter()
router.register('products', ProductViewSet, basename='product')
router.register('stocks', StockViewSet, basename='stock')
router.register('sales', SaleViewSet, basename='sale')

urlpatterns = [
    path('reports/', reports, name='reports'),
    *router.urls,
]
