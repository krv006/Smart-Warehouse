from rest_framework.routers import DefaultRouter
from apps.expenses.views import ExpenseTypeViewSet, ExpenseSubTypeViewSet, ExpenseViewSet

router = DefaultRouter()
router.register('expense-types',    ExpenseTypeViewSet,    basename='expense-type')
router.register('expense-subtypes', ExpenseSubTypeViewSet, basename='expense-subtype')
router.register('expenses',         ExpenseViewSet,        basename='expense')

urlpatterns = router.urls
