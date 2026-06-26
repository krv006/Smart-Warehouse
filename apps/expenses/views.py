from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions import IsAccountantOrManagement, IsAccountantOrReadOnly
from apps.expenses.models import ExpenseType, ExpenseSubType, Expense
from apps.expenses.serializers import (ExpenseTypeSerializer,
                                       ExpenseSubTypeSerializer, ExpenseSerializer)


@extend_schema_view(
    list=extend_schema(summary="Rasxod toifalari", tags=["Expenses"]),
    retrieve=extend_schema(summary="Toifa", tags=["Expenses"]),
    create=extend_schema(summary="Yangi toifa (Superuser)", tags=["Expenses"]),
    update=extend_schema(summary="Toifa yangilash", tags=["Expenses"]),
    partial_update=extend_schema(summary="Toifa qisman yangilash", tags=["Expenses"]),
    destroy=extend_schema(summary="Toifa o'chirish", tags=["Expenses"]),
)
class ExpenseTypeViewSet(ModelViewSet):
    queryset           = ExpenseType.objects.prefetch_related('sub_types')
    serializer_class   = ExpenseTypeSerializer
    permission_classes = (IsAuthenticated,)
    search_fields      = ('name', 'code')


@extend_schema_view(
    list=extend_schema(summary="Rasxod turlari", tags=["Expenses"]),
    retrieve=extend_schema(summary="Tur", tags=["Expenses"]),
    create=extend_schema(summary="Yangi tur (Accountant)", tags=["Expenses"]),
    update=extend_schema(summary="Tur yangilash", tags=["Expenses"]),
    partial_update=extend_schema(summary="Tur qisman yangilash", tags=["Expenses"]),
    destroy=extend_schema(summary="Tur o'chirish", tags=["Expenses"]),
)
class ExpenseSubTypeViewSet(ModelViewSet):
    queryset           = ExpenseSubType.objects.select_related('expense_type')
    serializer_class   = ExpenseSubTypeSerializer
    permission_classes = (IsAccountantOrReadOnly,)
    filterset_fields   = ('expense_type',)
    search_fields      = ('name',)


@extend_schema_view(
    list=extend_schema(
        summary="Rasxodlar ro'yxati",
        description="Filtr: `?expense_type=1`, `?currency=UZS`, `?date=2024-06-01`",
        tags=["Expenses"],
    ),
    retrieve=extend_schema(summary="Rasxod", tags=["Expenses"]),
    create=extend_schema(summary="Yangi rasxod (Accountant)", tags=["Expenses"]),
    update=extend_schema(summary="Rasxod yangilash", tags=["Expenses"]),
    partial_update=extend_schema(summary="Rasxod qisman yangilash", tags=["Expenses"]),
    destroy=extend_schema(summary="Rasxod o'chirish", tags=["Expenses"]),
)
class ExpenseViewSet(ModelViewSet):
    queryset           = Expense.objects.select_related(
        'expense_type', 'sub_type', 'responsible'
    )
    serializer_class   = ExpenseSerializer
    permission_classes = (IsAccountantOrReadOnly,)
    filterset_fields   = ('expense_type', 'sub_type', 'currency', 'date', 'responsible')
    search_fields      = ('expense_type__name', 'sub_type__name', 'comment')
    ordering_fields    = ('date', 'amount')
