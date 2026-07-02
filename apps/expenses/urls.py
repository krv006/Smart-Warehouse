from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.expenses.views import ExpenseTypeViewSet, ExpenseSubTypeViewSet, ExpenseViewSet

router = DefaultRouter()
router.register('expense-types',    ExpenseTypeViewSet,    basename='expense-type')
router.register('expense-subtypes', ExpenseSubTypeViewSet, basename='expense-subtype')
router.register('expenses',         ExpenseViewSet,        basename='expense')

# Legacy/alias: /api/v1/expenses/summary/ ham ishlashi uchun
# (asosiy manzil: /api/v1/expenses/expenses/summary/)
urlpatterns = [
    path('summary/', ExpenseViewSet.as_view({'get': 'summary'}),
         name='expense-summary-alias'),
] + router.urls
