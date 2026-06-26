from rest_framework.routers import DefaultRouter
from apps.warehouse.views import CategoryViewSet, ProductViewSet, StockViewSet

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('products',   ProductViewSet,  basename='product')
router.register('stocks',     StockViewSet,    basename='stock')

urlpatterns = router.urls
