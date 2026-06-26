from rest_framework.routers import DefaultRouter
from apps.expenses.views import ExpenseTypeViewSet, ExpenseSubTypeViewSet, ExpenseViewSet

router = DefaultRouter()
router.register('types',    ExpenseTypeViewSet,    basename='expense-type')
router.register('subtypes', ExpenseSubTypeViewSet, basename='expense-subtype')
router.register('',         ExpenseViewSet,        basename='expense')

urlpatterns = router.urls
