from django.utils.dateparse import parse_date

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsOperatorOrReadOnly, IsManagement
from apps.warehouse.models import Category, Product, Stock, STATUS_IN_STOCK, STATUS_LOW_STOCK, STATUS_OUT
from apps.warehouse.serializers import (CategorySerializer, ProductSerializer,
                                        ProductOperatorSerializer, StockSerializer)


@extend_schema_view(
    list=extend_schema(summary="Kategoriyalar daraxti", tags=["Warehouse"]),
    retrieve=extend_schema(summary="Kategoriya", tags=["Warehouse"]),
    create=extend_schema(summary="Yangi kategoriya", tags=["Warehouse"]),
    update=extend_schema(summary="Kategoriya yangilash", tags=["Warehouse"]),
    partial_update=extend_schema(summary="Kategoriya qisman yangilash", tags=["Warehouse"]),
    destroy=extend_schema(summary="Kategoriya o'chirish", tags=["Warehouse"]),
)
class CategoryViewSet(ModelViewSet):
    serializer_class   = CategorySerializer
    permission_classes = (IsOperatorOrReadOnly,)
    search_fields      = ('name',)

    def get_queryset(self):
        if self.action == 'list':
            return Category.objects.root_nodes().prefetch_related(
                'children__children__children'
            )
        return Category.objects.all()


@extend_schema_view(
    list=extend_schema(summary="Mahsulotlar ro'yxati", tags=["Warehouse"]),
    retrieve=extend_schema(summary="Mahsulot", tags=["Warehouse"]),
    create=extend_schema(summary="Yangi mahsulot (Operator)", tags=["Warehouse"]),
    update=extend_schema(summary="Mahsulot yangilash", tags=["Warehouse"]),
    partial_update=extend_schema(summary="Mahsulot qisman yangilash", tags=["Warehouse"]),
    destroy=extend_schema(summary="Mahsulot o'chirish", tags=["Warehouse"]),
)
class ProductViewSet(ModelViewSet):
    queryset           = Product.objects.select_related('category').all()
    permission_classes = (IsOperatorOrReadOnly,)
    search_fields      = ('name', 'model', 'serial_number', 'source')
    ordering_fields    = ('name', 'purchase_price', 'created_at')
    filterset_fields   = {
        'category':       ['exact'],
        'purchase_price': ['isnull'],
        'selling_price':  ['isnull'],
    }

    def get_serializer_class(self):
        user = self.request.user
        if user.is_authenticated and getattr(user, 'is_management', False):
            return ProductSerializer
        return ProductOperatorSerializer

    @extend_schema(
        summary="Mahsulotning shartnomalari (reestr)",
        description=(
            "Shu mahsulotga bog'langan BARCHA shartnoma yozuvlari — har bir "
            "holat (buyurtma yaratildi/tahrirlandi, zakaz tasdiqlandi/"
            "yuborildi/qabul qilindi...) o'z shartnoma raqami, asosi va "
            "sanasi bilan. Davlat va mijozlar oldida asos."
        ),
        tags=["Warehouse"],
    )
    @action(detail=True, methods=['get'])
    def contracts(self, request, pk=None):
        from apps.orders.serializers import ProductContractSerializer
        product = self.get_object()
        qs = (product.contracts
              .select_related('order', 'zakaz', 'created_by')
              .order_by('-created_at'))
        return Response(ProductContractSerializer(qs, many=True).data)


@extend_schema_view(
    list=extend_schema(
        summary="Ombor qoldiqlari (Ostatka)", tags=["Warehouse"],
        description="Filtr: `?product=1`, `?warehouse_location=A-1`"
    ),
    retrieve=extend_schema(summary="Qoldiq", tags=["Warehouse"]),
    create=extend_schema(summary="Yangi qoldiq (Operator)", tags=["Warehouse"]),
    update=extend_schema(summary="Qoldiq yangilash", tags=["Warehouse"]),
    partial_update=extend_schema(summary="Qoldiq qisman yangilash", tags=["Warehouse"]),
    destroy=extend_schema(summary="Qoldiq o'chirish", tags=["Warehouse"]),
)
class StockViewSet(ModelViewSet):
    serializer_class   = StockSerializer
    permission_classes = (IsOperatorOrReadOnly,)
    filterset_fields   = ('product', 'warehouse_location')
    search_fields      = ('product__name', 'product__serial_number', 'warehouse_location')

    def get_queryset(self):
        qs = Stock.objects.select_related('product', 'product__category')
        params = self.request.query_params

        category = params.get('category')
        if category:
            qs = qs.filter(product__category_id=category)

        date_from = params.get('date_from')
        date_to   = params.get('date_to')
        if date_from:
            qs = qs.filter(created_at__date__gte=parse_date(date_from))
        if date_to:
            qs = qs.filter(created_at__date__lte=parse_date(date_to))

        status = params.get('status')
        if status == STATUS_OUT:
            qs = qs.filter(quantity=0)
        elif status == STATUS_LOW_STOCK:
            # quantity > 0 and quantity <= product.min_quantity
            from django.db.models import F
            qs = qs.filter(quantity__gt=0, quantity__lte=F('product__min_quantity'))
        elif status == STATUS_IN_STOCK:
            from django.db.models import F
            qs = qs.filter(quantity__gt=F('product__min_quantity'))

        return qs
