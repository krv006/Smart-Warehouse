from django.db import transaction
from django.db.models import F
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
        summary="Kirim — mahsulot keldi (omborni to'ldirish)",
        description=(
            "Omborda BOR mahsulotdan yana kelganda ishlatiladi (stock sonini "
            "qo'lda tahrirlash o'rniga to'g'ri hujjatli yo'l).\n\n"
            "```json\n"
            "{\n"
            '  "quantity": 20,\n'
            '  "warehouse_location": "B-2-3",\n'
            '  "asos": "Kirim orderi №77",\n'
            '  "contract_number": "SH-2026/051",\n'
            '  "faktura": "F-2026/900"\n'
            "}\n"
            "```\n\n"
            "- `quantity` va `asos` — MAJBURIY (asossiz kirim yo'q)\n"
            "- `warehouse_location` bo'sh bo'lsa — `Asosiy ombor`\n"
            "- Qoldiq oshadi va **kutayotgan buyurtmalarga avtomatik bron** "
            "ajratiladi (har biri tarixga shartnoma asosida yoziladi)\n"
            "- Kirim mahsulot **shartnomalar reestriga** (`stock_in`) tushadi\n"
            "- Low-stock bildirishnoma avtomatik yopiladi"
        ),
        tags=["Warehouse"],
    )
    @action(detail=True, methods=['post'], url_path='add-stock')
    def add_stock(self, request, pk=None):
        from apps.orders.models import (ProductContract, register_contract,
                                        allocate_pending_orders, OrderHistory)
        from apps.notifications.models import Notification
        from apps.orders.models import OrderItem, Order

        product = self.get_object()

        # Majburiy maydonlar
        try:
            qty = int(request.data.get('quantity') or 0)
        except (TypeError, ValueError):
            qty = 0
        if qty <= 0:
            return Response(
                {'quantity': 'Kirim miqdori musbat son bo\'lishi kerak.'},
                status=400)
        asos = request.data.get('asos')
        if not asos:
            return Response(
                {'asos': 'Kirim uchun asos kiritilishi shart '
                         '(masalan: "Kirim orderi №77").'},
                status=400)

        loc             = request.data.get('warehouse_location') or 'Asosiy ombor'
        contract_number = request.data.get('contract_number')
        faktura         = request.data.get('faktura')

        with transaction.atomic():
            stock, _ = Stock.objects.select_for_update().get_or_create(
                product=product, warehouse_location=loc,
                defaults={'quantity': 0, 'reserved_quantity': 0},
            )
            stock.quantity = F('quantity') + qty
            stock.save(update_fields=['quantity'])
            stock.refresh_from_db()

            # Kutayotgan buyurtmalarga avtomatik bron + tarixga iz
            pending_items = OrderItem.objects.filter(
                product=product,
                order__status__in=(Order.PENDING, Order.PARTIAL))
            before = {i.pk: i.reserved_qty for i in pending_items}
            allocate_pending_orders(product)
            gained_by_order = {}
            for i in (OrderItem.objects.filter(pk__in=before)
                      .select_related('order')):
                gained = i.reserved_qty - before[i.pk]
                if gained > 0:
                    gained_by_order.setdefault(i.order, 0)
                    gained_by_order[i.order] += gained
            for order, gained in gained_by_order.items():
                OrderHistory.objects.create(
                    order=order, changed_by=request.user,
                    action=OrderHistory.ALLOCATED,
                    contract_number=contract_number,
                    asos=(f'Kirim ({asos}'
                          + (f', shartnoma №{contract_number}' if contract_number else '')
                          + (f', faktura {faktura}' if faktura else '')
                          + f') — {gained} dona avtomatik bron ajratildi.'),
                )

            # Shartnomalar reestriga kirim yozuvi
            register_contract(
                product, ProductContract.STOCK_IN,
                contract_number=contract_number,
                faktura=faktura,
                asos=asos,
                user=request.user,
            )

        # Low-stock bildirishnomani yop (agar qoldiq etarli bo'lsa)
        if product.available_quantity > product.min_quantity:
            Notification.resolve_low_stock_notifications(product)

        return Response({
            'detail':             f'{qty} dona kirim qilindi ({loc}).',
            'stock':              {'id': stock.pk,
                                   'warehouse_location': stock.warehouse_location,
                                   'quantity': stock.quantity,
                                   'reserved_quantity': stock.reserved_quantity},
            'quantity_in_stock':  product.quantity_in_stock,
            'reserved_quantity':  product.reserved_quantity,
            'available_quantity': product.available_quantity,
            'allocated_orders':   [{'order': o.pk, 'allocated': g}
                                   for o, g in gained_by_order.items()],
        }, status=201)

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
