from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsOperatorOrReadOnly, IsManagement
from apps.warehouse.models import Category, Product, Stock
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
    }

    def get_serializer_class(self):
        user = self.request.user
        if user.is_authenticated and getattr(user, 'is_management', False):
            return ProductSerializer
        return ProductOperatorSerializer


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
    queryset           = Stock.objects.select_related('product', 'product__category')
    serializer_class   = StockSerializer
    permission_classes = (IsOperatorOrReadOnly,)
    filterset_fields   = ('product', 'warehouse_location')
    search_fields      = ('product__name', 'product__serial_number', 'warehouse_location')
