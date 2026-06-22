from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.models import Product, Stock, Sale
from apps.permissions import IsOperatorOrReadOnly, IsManagement
from apps.serializers import ProductSerializer, StockSerializer, SaleSerializer


class ProductViewSet(ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = (IsOperatorOrReadOnly,)
    # TZ: real-time qidiruv — nom, model, seriya raqami bo'yicha
    search_fields = ('name', 'model', 'serial_number')
    ordering_fields = ('name', 'purchase_price', 'created_at')


class StockViewSet(ModelViewSet):
    queryset = Stock.objects.select_related('product')
    serializer_class = StockSerializer
    permission_classes = (IsOperatorOrReadOnly,)
    filterset_fields = ('product', 'warehouse_location')
    search_fields = ('product__name', 'product__serial_number', 'warehouse_location')


class SaleViewSet(ModelViewSet):
    queryset = Sale.objects.select_related('product')
    serializer_class = SaleSerializer
    permission_classes = (IsOperatorOrReadOnly,)
    filterset_fields = ('product', 'sold_date')
    search_fields = ('product__name', 'sold_to')
    ordering_fields = ('sold_date', 'sold_price', 'quantity')


@api_view(['GET'])
@permission_classes([IsManagement])
def reports(request):
    """
    TZ: Management uchun hisobot — sotuv monitoringi, foyda hisoblash.
    """
    profit_expr = ExpressionWrapper(
        (F('sold_price') - F('product__purchase_price')) * F('quantity'),
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )
    revenue_expr = ExpressionWrapper(
        F('sold_price') * F('quantity'),
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )

    sales = Sale.objects.all()
    totals = sales.aggregate(
        total_revenue=Sum(revenue_expr),
        total_profit=Sum(profit_expr),
        total_units_sold=Sum('quantity'),
    )

    by_product = list(
        sales.values('product', 'product__name')
        .annotate(
            revenue=Sum(revenue_expr),
            profit=Sum(profit_expr),
            units_sold=Sum('quantity'),
        )
        .order_by('-profit')
    )

    return Response({
        'sales_count': sales.count(),
        'total_revenue': totals['total_revenue'] or 0,
        'total_profit': totals['total_profit'] or 0,
        'total_units_sold': totals['total_units_sold'] or 0,
        'total_stock_units': Stock.objects.aggregate(t=Sum('quantity'))['t'] or 0,
        'products_count': Product.objects.count(),
        'by_product': by_product,
    })
