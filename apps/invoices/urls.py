from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.invoices.views import ElectronicInvoiceViewSet

router = DefaultRouter()
router.register('', ElectronicInvoiceViewSet, basename='e-invoice')

urlpatterns = [
    path('', include(router.urls)),
]
