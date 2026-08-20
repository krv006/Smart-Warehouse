from django.db import transaction
from django.db.models import F, Q
from django.utils.dateparse import parse_date

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsOperatorOrManagementWrite, IsManagement
from apps.warehouse.models import (Product, Stock, STATUS_IN_STOCK, STATUS_LOW_STOCK,
                                   STATUS_OUT, STATUS_ON_THE_WAY)
from apps.warehouse.serializers import (ProductSerializer,
                                        ProductOperatorSerializer,
                                        ProductAccountantSerializer, StockSerializer)


# Kategoriya funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
# @extend_schema_view(
#     list=extend_schema(summary="Kategoriyalar daraxti", tags=["Warehouse"]),
#     retrieve=extend_schema(summary="Kategoriya", tags=["Warehouse"]),
#     create=extend_schema(summary="Yangi kategoriya", tags=["Warehouse"]),
#     update=extend_schema(summary="Kategoriya yangilash", tags=["Warehouse"]),
#     partial_update=extend_schema(summary="Kategoriya qisman yangilash", tags=["Warehouse"]),
#     destroy=extend_schema(summary="Kategoriya o'chirish", tags=["Warehouse"]),
# )
# class CategoryViewSet(ModelViewSet):
#     serializer_class   = CategorySerializer
#     permission_classes = (IsOperatorOrManagementWrite,)
#     search_fields      = ('name',)
#
#     def get_queryset(self):
#         if self.action == 'list':
#             return Category.objects.root_nodes().prefetch_related(
#                 'children__children__children'
#             )
#         return Category.objects.all()


@extend_schema_view(
    list=extend_schema(summary="Mahsulotlar ro'yxati", tags=["Warehouse"]),
    retrieve=extend_schema(summary="Mahsulot", tags=["Warehouse"]),
    create=extend_schema(summary="Yangi mahsulot (Operator)", tags=["Warehouse"]),
    update=extend_schema(summary="Mahsulot yangilash", tags=["Warehouse"]),
    partial_update=extend_schema(summary="Mahsulot qisman yangilash", tags=["Warehouse"]),
    destroy=extend_schema(summary="Mahsulot o'chirish", tags=["Warehouse"]),
)
class ProductViewSet(ModelViewSet):
    # stocks/zakazlar — qoldiq va "yo'ldagi import" miqdori uchun (N+1 oldini olish)
    queryset           = (Product.objects
                          .prefetch_related('stocks', 'zakazlar').all())
    permission_classes = (IsOperatorOrManagementWrite,)
    # Model funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi: 'model' qidiruvdan olib tashlandi.
    search_fields      = ('name', 'serial_number', 'source')
    ordering_fields    = ('name', 'purchase_price', 'created_at')
    filterset_fields   = {
        'purchase_price': ['isnull'],
        'selling_price':  ['isnull'],
    }

    def get_serializer_class(self):
        user = self.request.user
        if user.is_authenticated and getattr(user, 'is_management', False):
            return ProductSerializer
        if user.is_authenticated and getattr(user, 'is_accountant', False):
            return ProductAccountantSerializer
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

            # Kelish narxi bo'lsa — kirim summasi kassadan chiqim (Expense)
            # sifatida yoziladi
            from apps.warehouse.stock_expense import record_stock_in_expense
            record_stock_in_expense(
                product, qty, user=request.user, asos=asos,
                contract_number=contract_number, faktura=faktura,
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


def _pending_product_ids_subquery():
    """Faol (hali qabul qilinmagan) Zakaz/Kirim'i bor mahsulotlar ID'lari.

    `Product.pending_import_quantity` bilan bir xil mantiq (har bir Zakaz
    qatori uchun `max(quantity - received_qty, 0)`, keyin mahsulot bo'yicha
    yig'indi > 0) — lekin bu yerda subquery sifatida, Python'ga barcha Zakaz
    qatorlarini yuklamasdan ishlatiladi.
    """
    from django.db.models import Sum
    from django.db.models.functions import Greatest
    from apps.orders.models import Zakaz

    return (
        Zakaz.objects
        .filter(status__in=Zakaz.ACTIVE_STATUSES)
        .annotate(shortfall=Greatest(F('quantity') - F('received_qty'), 0))
        .values('product_id')
        .annotate(total_pending=Sum('shortfall'))
        .filter(total_pending__gt=0)
        .values_list('product_id', flat=True)
    )


@extend_schema_view(
    list=extend_schema(
        summary="Ombor qoldiqlari (Ostatka)", tags=["Warehouse"],
        description=(
            "Filtr: `?product=1`, `?warehouse_location=A-1`, "
            "`?status=out_of_stock|low_stock|in_stock|on_the_way`\n\n"
            "**Standart ko'rinish** (status berilmasa): qoldig'i 0 VA hech "
            "qanday yo'ldagi (faol Zakaz/Kirim) miqdori yo'q mahsulotlar "
            "ro'yxatdan yashiriladi. Qoldig'i 0 bo'lsa-da yo'lda importi bor "
            "mahsulotlar `on_the_way` (\"Yo'lda\") holatida ko'rinishda "
            "qoladi — hatto hali birorta ham Stock qatori yaratilmagan "
            "(hammasi yo'lda) mahsulot uchun ham sintetik qator qo'shiladi. "
            "`?status=out_of_stock` — chinakam bo'sh (yo'lda ham hech narsa "
            "yo'q) qatorlarni ko'rish uchun aniq so'ralishi kerak."
        ),
    ),
    retrieve=extend_schema(summary="Qoldiq", tags=["Warehouse"]),
    create=extend_schema(summary="Yangi qoldiq (Operator)", tags=["Warehouse"]),
    update=extend_schema(summary="Qoldiq yangilash", tags=["Warehouse"]),
    partial_update=extend_schema(summary="Qoldiq qisman yangilash", tags=["Warehouse"]),
    destroy=extend_schema(summary="Qoldiq o'chirish", tags=["Warehouse"]),
)
class StockViewSet(ModelViewSet):
    serializer_class   = StockSerializer
    permission_classes = (IsOperatorOrManagementWrite,)
    filterset_fields   = ('product', 'warehouse_location')
    search_fields      = ('product__name', 'product__serial_number', 'warehouse_location')
    ordering_fields    = ('quantity', 'created_at', 'product__name')

    def perform_destroy(self, instance):
        # Broni bor qatorni o'chirish buyurtmalardagi reserved_qty hisobini
        # havoda qoldiradi
        if instance.reserved_quantity > 0:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                f'Bu qoldiqda {instance.reserved_quantity} dona bron bor — '
                'avval tegishli buyurtmalarni bekor qiling.')
        super().perform_destroy(instance)

    def get_queryset(self):
        # `product__zakazlar` — StockSerializer.get_stock_status() har bir
        # qator uchun `product.pending_import_quantity` ("Yo'lda") ni
        # hisoblaydi, u esa `product.zakazlar.all()` ni aylanadi — shu
        # prefetch bo'lmasa har bir qator uchun alohida so'rov ketadi.
        qs = Stock.objects.select_related('product').prefetch_related('product__zakazlar')
        params = self.request.query_params

        date_from = params.get('date_from')
        date_to   = params.get('date_to')
        if date_from:
            qs = qs.filter(created_at__date__gte=parse_date(date_from))
        if date_to:
            qs = qs.filter(created_at__date__lte=parse_date(date_to))

        pending_ids = _pending_product_ids_subquery()
        status = params.get('status')
        if status == STATUS_OUT:
            # Chinakam bo'sh — yo'lda hech narsa yo'q
            qs = qs.filter(quantity=0).exclude(product_id__in=pending_ids)
        elif status == STATUS_LOW_STOCK:
            # quantity > 0 and quantity <= product.min_quantity
            qs = qs.filter(quantity__gt=0, quantity__lte=F('product__min_quantity'))
        elif status == STATUS_IN_STOCK:
            qs = qs.filter(quantity__gt=F('product__min_quantity'))
        elif status == STATUS_ON_THE_WAY:
            qs = qs.filter(quantity=0, product_id__in=pending_ids)
        elif self.action == 'list':
            # Standart ro'yxat ko'rinishi: status filtri berilmagan bo'lsa,
            # butunlay bo'sh VA yo'lda hech narsasi yo'q qatorlar
            # yashiriladi. retrieve/update/destroy uchun bu cheklov
            # qo'llanilmaydi — mavjud (hatto 0 qoldiqli) qatorni tahrirlash/
            # o'chirish har doim ishlashi kerak.
            qs = qs.filter(Q(quantity__gt=0) | Q(product_id__in=pending_ids))

        return qs

    def _synthetic_pending_rows(self, status):
        """Birorta ham Stock qatori yo'q, lekin yo'lda (faol Zakaz/Kirim)
        miqdori bor mahsulotlar uchun DB'ga yozilmagan `Stock` obyektlari —
        StockSerializer ular bilan ham to'liq ishlay oladi (product FK
        o'rnatilgan, id=None). Faqat status filtri qo'llanilmagan yoki aynan
        `on_the_way` so'ralganda, va joylashuv (`warehouse_location`) filtri
        yo'q paytda qo'shiladi — sintetik qatorlarning real joylashuvi yo'q.
        """
        if status not in (None, '', STATUS_ON_THE_WAY):
            return []
        params = self.request.query_params
        if params.get('warehouse_location'):
            return []

        products = Product.objects.filter(
            stocks__isnull=True, id__in=_pending_product_ids_subquery())

        product_id = params.get('product')
        if product_id:
            products = products.filter(pk=product_id)

        search = params.get('search')
        if search:
            products = products.filter(
                Q(name__icontains=search) | Q(serial_number__icontains=search))

        return [
            Stock(product=product, quantity=0, reserved_quantity=0, warehouse_location='')
            for product in products
        ]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        status = request.query_params.get('status')
        combined = list(queryset) + self._synthetic_pending_rows(status)

        page = self.paginate_queryset(combined)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(combined, many=True)
        return Response(serializer.data)
