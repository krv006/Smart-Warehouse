from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.views import (ProductViewSet, StockViewSet, SaleViewSet,
                        reports, login, register_operator)

router = DefaultRouter()
router.register('products', ProductViewSet, basename='product')
router.register('stocks', StockViewSet, basename='stock')
router.register('sales', SaleViewSet, basename='sale')

urlpatterns = [
    # Auth
    path('auth/login/',             login,                                name='login'),
    path('auth/token/refresh/',     TokenRefreshView.as_view(),           name='token-refresh'),
    path('auth/register-operator/', register_operator,                    name='register-operator'),

    # Hisobot
    path('reports/', reports, name='reports'),

    *router.urls,
]
