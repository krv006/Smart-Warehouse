from django.db.models import Sum, Q

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework.decorators import action
from rest_framework.response import Response
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
    serializer_class   = ExpenseSerializer
    permission_classes = (IsAccountantOrReadOnly,)
    filterset_fields   = {
        'expense_type': ['exact'],
        'sub_type':     ['exact'],
        'currency':     ['exact'],
        'responsible':  ['exact'],
    }
    search_fields      = ('expense_type__name', 'sub_type__name', 'comment')
    ordering_fields    = ('date', 'amount')

    def get_queryset(self):
        qs = Expense.objects.select_related('expense_type', 'sub_type', 'responsible')
        p  = self.request.query_params
        if p.get('date_from'):
            qs = qs.filter(date__gte=p['date_from'])
        if p.get('date_to'):
            qs = qs.filter(date__lte=p['date_to'])
        return qs

    @extend_schema(
        summary="Rasxodlar xulosasi (statistika)",
        parameters=[
            OpenApiParameter('date_from', str, description='YYYY-MM-DD'),
            OpenApiParameter('date_to',   str, description='YYYY-MM-DD'),
            OpenApiParameter('currency',  str, description='UZS yoki USD'),
        ],
        tags=["Expenses"],
    )
    @action(detail=False, methods=['get'], url_path='summary',
            permission_classes=[IsAccountantOrManagement])
    def summary(self, request):
        qs = self.get_queryset()

        total_uzs = qs.filter(currency=Expense.UZS).aggregate(t=Sum('amount'))['t'] or 0
        total_usd = qs.filter(currency=Expense.USD).aggregate(t=Sum('amount'))['t'] or 0

        by_type = []
        for et in ExpenseType.objects.all():
            t_uzs = qs.filter(expense_type=et, currency=Expense.UZS).aggregate(t=Sum('amount'))['t'] or 0
            t_usd = qs.filter(expense_type=et, currency=Expense.USD).aggregate(t=Sum('amount'))['t'] or 0
            if t_uzs or t_usd:
                by_type.append({
                    'expense_type': et.id,
                    'name':         et.name,
                    'total_uzs':    str(t_uzs),
                    'total_usd':    str(t_usd),
                })

        return Response({
            'total_uzs': str(total_uzs),
            'total_usd': str(total_usd),
            'by_type':   by_type,
            'count':     qs.count(),
        })
