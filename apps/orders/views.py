from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.mixins import (CreateModelMixin, ListModelMixin,
                                   RetrieveModelMixin, UpdateModelMixin)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.common.permissions import IsOperatorOrReadOnly
from apps.orders.models import (Order, OrderHistory, Zakaz, ZakazHistory,
                                ProductContract, register_contract,
                                allocate_pending_orders)
from apps.orders.serializers import (OrderSerializer, ZakazSerializer,
                                     OrderBulkCreateSerializer,
                                     ZakazBulkCreateSerializer,
                                     ProductContractSerializer)


# ── Order (Bron) ──────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        summary="Buyurtmalar / Bron ro'yxati",
        description=(
            "Filtr: `?status=pending|partial|reserved|fulfilled|cancelled`, "
            "`?product=1`, `?client=<uuid>`, `?contract_number=SH-2026/045`"
        ),
        tags=["Orders / Bron"],
    ),
    retrieve=extend_schema(summary="Buyurtma (tarixi bilan)", tags=["Orders / Bron"]),
    create=extend_schema(
        summary="Yangi buyurtma (Operator / Manager)",
        description=(
            "**BITTA buyurtma — bir nechta mahsulot (`items`).** Nechta mahsulot "
            "bo'lishidan qat'i nazar buyurtma bitta hujjat bo'ladi.\n\n"
            "```json\n"
            "{\n"
            '  "client": "<uuid>",\n'
            '  "contract_number": "SH-2026/045",\n'
            '  "prepaid_amount": "5000000",\n'
            '  "due_date": "2026-08-01",\n'
            '  "items": [\n'
            '    { "product": 12, "quantity": 4, "unit_price": "3900000" },\n'
            '    { "product": 7,  "quantity": 2, "unit_price": "1200000" }\n'
            "  ]\n"
            "}\n"
            "```\n\n"
            "**Shartnoma raqami (`contract_number`) MAJBURIY.** "
            "`contract_date` yuborilmasa — bugungi kun (Tashkent).\n\n"
            "`prepaid_amount` — oldindan to'langan summa (kassaga tushadi). "
            "`balance_due` = total − prepaid_amount.\n\n"
            "- Har qatorga ombordan FIFO bron ajratiladi\n"
            "- Yetishmagan (backorder) qatorlar uchun **AVTOMATIK Zakaz** ochiladi — "
            "o'sha shartnoma raqami asosida\n"
            "- Eski format (`product`+`quantity`+`unit_price` to'g'ridan-to'g'ri) "
            "ham qabul qilinadi — bitta qatorli buyurtma bo'ladi\n\n"
            "Yangi qoldiq kelganida pending/partial buyurtmalar **avtomatik** bronlanadi."
        ),
        tags=["Orders / Bron"],
    ),
    partial_update=extend_schema(
        summary="Buyurtma tahrirlash (bir necha bor mumkin, asos majburiy)",
        description=(
            "Buyurtmani bir necha bor tahrirlash mumkin. Har tahrirda **`asos`** "
            "(tahrir sababi) MAJBURIY — tahrir shartnoma raqami, asos va aniq "
            "sana/vaqt bilan tarixga (`history`) yoziladi.\n\n"
            "Miqdor o'zgartirilsa bron avtomatik qayta moslanadi. "
            "Tahrir Zakaz qismiga ta'sir qilmaydi."
        ),
        tags=["Orders / Bron"],
    ),
)
class OrderViewSet(CreateModelMixin, ListModelMixin,
                   RetrieveModelMixin, UpdateModelMixin, GenericViewSet):
    """
    Buyurtma / Bron.
    O'chirish yo'q — buning o'rniga /cancel/ action ishlatiladi.
    PATCH — tahrirlash (asos majburiy, tarixga yoziladi).
    """
    queryset           = (Order.objects
                          .select_related('client')
                          .prefetch_related('items__product',
                                            'history__changed_by'))
    serializer_class   = OrderSerializer
    permission_classes = (IsOperatorOrReadOnly,)
    filterset_fields   = {
        'status':          ['exact'],
        'client':          ['exact'],
        'contract_number': ['exact'],
        'items__product':  ['exact'],
    }
    search_fields      = ('items__product__name', 'items__product__serial_number',
                          'client__company_name', 'contract_number', 'comment')
    ordering_fields    = ('due_date', 'created_at', 'status')
    http_method_names  = ('get', 'post', 'patch', 'head', 'options')

    @extend_schema(
        summary="Bir nechta mahsulotli buyurtma (bulk) — natija BITTA buyurtma",
        description=(
            "Bitta client/due_date/**shartnoma** ostida bir nechta mahsulot "
            "buyurtma qilinadi. **Natija — BITTA buyurtma**, ichida qatorlar "
            "(`items`). Yetishmagan qatorlar uchun avtomatik Zakaz ochiladi.\n\n"
            "`POST /orders/` ning o'zi ham `items` ni qabul qiladi — bu endpoint "
            "moslik uchun saqlangan.\n\n"
            "```json\n"
            "{\n"
            '  "client": "<uuid>",\n'
            '  "due_date": "2026-08-01",\n'
            '  "contract_number": "SH-2026/045",\n'
            '  "prepaid_amount": "5000000",\n'
            '  "items": [\n'
            '    { "product": 12, "quantity": 4, "unit_price": "3900000" },\n'
            '    { "product": 7,  "quantity": 2, "unit_price": "1200000" }\n'
            "  ]\n"
            "}\n"
            "```"
        ),
        request=OrderBulkCreateSerializer,
        tags=["Orders / Bron"],
    )
    @action(detail=False, methods=['post'])
    def bulk(self, request):
        serializer = OrderBulkCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(
            OrderBulkCreateSerializer().to_representation(order),
            status=201,
        )

    @extend_schema(
        summary="Buyurtmani yetkazildi deb belgilash",
        description=(
            "Bron qilingan miqdor ombor qoldiqidan ayiriladi. "
            "Boshqa pending buyurtmalarga avtomatik bron qayta ajratiladi. "
            "Amal tarixga yoziladi (ixtiyoriy body: `{ \"asos\": \"...\" }`)."
        ),
        tags=["Orders / Bron"],
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def fulfill(self, request, pk=None):
        order = self.get_object()
        if order.status == Order.FULFILLED:
            return Response(
                {'detail': 'Buyurtma allaqachon yetkazilgan.'},
                status=400,
            )
        if order.status == Order.CANCELLED:
            return Response(
                {'detail': 'Bekor qilingan buyurtmani yetkazib bo\'lmaydi.'},
                status=400,
            )
        if order.reserved_qty == 0:
            return Response(
                {'detail': 'Bron qilingan miqdor yo\'q. Avval omborda qoldiq bo\'lishi kerak.'},
                status=400,
            )
        order.fulfill()
        asos = request.data.get('asos') or 'Buyurtma yetkazildi.'
        OrderHistory.objects.create(
            order=order, changed_by=request.user, action=OrderHistory.FULFILLED,
            contract_number=order.contract_number,
            asos=asos,
        )
        for item in order.items.all():
            register_contract(
                item.product, ProductContract.ORDER_FULFILLED,
                contract_number=order.contract_number,
                contract_date=order.contract_date,
                asos=asos, order=order, user=request.user,
            )
        return Response(OrderSerializer(order).data)

    @extend_schema(
        summary="Buyurtmani bekor qilish (bron bo'shatiladi)",
        description=(
            "Bron bo'shatiladi va boshqa pending buyurtmalarga ajratiladi. "
            "Amal tarixga yoziladi (ixtiyoriy body: `{ \"asos\": \"...\" }`)."
        ),
        tags=["Orders / Bron"],
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status in (Order.FULFILLED, Order.CANCELLED):
            return Response(
                {'detail': f'"{order.get_status_display()}" holatidagi buyurtmani bekor qilib bo\'lmaydi.'},
                status=400,
            )
        order.release()
        order.status = Order.CANCELLED
        order.save(update_fields=['status'])
        asos = request.data.get('asos') or 'Buyurtma bekor qilindi.'
        OrderHistory.objects.create(
            order=order, changed_by=request.user, action=OrderHistory.CANCELLED,
            contract_number=order.contract_number,
            asos=asos,
        )
        for item in order.items.all():
            allocate_pending_orders(item.product)
            register_contract(
                item.product, ProductContract.ORDER_CANCELLED,
                contract_number=order.contract_number,
                contract_date=order.contract_date,
                asos=asos, order=order, user=request.user,
            )
        return Response(OrderSerializer(order).data)

    @extend_schema(
        summary="Buyurtmadagi yetishmagan miqdorga zakaz berish (qo'lda)",
        description=(
            "Odatda zakaz buyurtma yaratilganda **avtomatik** ochiladi. Bu endpoint "
            "avtomatik zakaz ochilmagan/bekor qilingan holatlar uchun.\n\n"
            "Buyurtmadagi `backorder_qty` (yetishmagan miqdor) uchun Zakaz yozuvi "
            "yaratadi — buyurtma va **shartnoma raqami asosida** bog'lanadi.\n\n"
            "Ixtiyoriy body: `{ \"supplier\": \"...\", \"expected_date\": \"2026-08-01\" }`"
        ),
        request=None,
        tags=["Orders / Bron"],
    )
    @action(detail=True, methods=['post'], url_path='create-zakaz',
            permission_classes=[IsAuthenticated])
    def create_zakaz(self, request, pk=None):
        order = self.get_object()
        if order.backorder_qty <= 0:
            return Response(
                {'detail': 'Bu buyurtmada zakaz kerak bo\'lgan (yetishmagan) miqdor yo\'q.'},
                status=400,
            )
        zakazlar = order.create_backorder_zakaz(user=request.user)
        if not zakazlar:
            return Response(
                {'detail': 'Zakaz yaratilmadi — yetishmagan mahsulotlar uchun '
                           'faol zakaz allaqachon mavjud.'},
                status=400,
            )
        # Ixtiyoriy supplier/expected_date qayta yozish (hammасига)
        supplier      = request.data.get('supplier')
        expected_date = request.data.get('expected_date')
        for zakaz in zakazlar:
            update_fields = []
            if supplier:
                zakaz.supplier = supplier
                update_fields.append('supplier')
            if expected_date:
                zakaz.expected_date = expected_date
                update_fields.append('expected_date')
            if update_fields:
                zakaz.save(update_fields=update_fields)
        return Response(
            {'zakazlar': ZakazSerializer(zakazlar, many=True).data},
            status=201,
        )


# ── Zakaz (Etkazuvchidan buyurtma) ────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        summary="Zakazlar ro'yxati",
        description=(
            "Filtr: `?status=new|confirmed|ordered|received|cancelled`, `?product=1`, "
            "`?order=5`, `?contract_number=SH-2026/045`\n\n"
            "Operator yaratadi (yoki buyurtmadan avtomatik). "
            "Status faqat Manager tomonidan o'zgartiriladi."
        ),
        tags=["Zakaz"],
    ),
    retrieve=extend_schema(summary="Zakaz (tarixi bilan)", tags=["Zakaz"]),
    create=extend_schema(
        summary="Yangi zakaz (Operator / Manager)",
        description=(
            "Status avtomatik `new` qilib saqlanadi.\n\n"
            "Odatda zakaz buyurtmadagi yetishmagan miqdor uchun **avtomatik** "
            "ochiladi (shartnoma raqami bilan birga).\n\n"
            "`received_qty` va status o'zgartirish faqat Manager uchun (PATCH orqali)."
        ),
        tags=["Zakaz"],
    ),
    partial_update=extend_schema(
        summary="Zakaz yangilash — status, received_qty (faqat Manager)",
        description=(
            "**Operator:** faqat `supplier`, `expected_date`, `comment`, "
            "`warehouse_location`, `asos`, `faktura` o'zgartira oladi.\n\n"
            "**Manager:** `status` va `received_qty` ham o'zgartira oladi.\n\n"
            "**Tasdiqlash (`confirmed`):** `contract_number` (dogovor) "
            "kiritilmaguncha tasdiqlab BO'LMAYDI. Shartnoma sanasi bo'sh bo'lsa "
            "avtomatik bugungi kun (Tashkent) qo'yiladi; buyurtmadan kelgan "
            "shartnomada o'sha kun saqlanadi. `confirmed_at` — aniq sana/vaqt.\n\n"
            "**Qabul qilish (`received`):** `asos` va `faktura` MAJBURIY. "
            "`received_qty` ombor qoldig'iga qo'shiladi va pending buyurtmalarga "
            "avtomatik bron ajratiladi.\n\n"
            "Har bir o'zgarish tarixga (`history`) yoziladi."
        ),
        tags=["Zakaz"],
    ),
)
class ZakazViewSet(CreateModelMixin, ListModelMixin,
                   RetrieveModelMixin, UpdateModelMixin, GenericViewSet):
    """
    Zakaz (procurement order).
    Operator: yaratadi + supplier/comment/expected_date/asos/faktura o'zgartiradi.
    Manager: status + received_qty o'zgartiradi.
    O'chirish: admin panel orqali.
    """
    queryset           = (Zakaz.objects
                          .select_related('product', 'created_by', 'order')
                          .prefetch_related('history__changed_by'))
    serializer_class   = ZakazSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields   = {
        'status':          ['exact'],
        'product':         ['exact'],
        'order':           ['exact'],
        'contract_number': ['exact'],
    }
    search_fields      = ('product__name', 'product__serial_number',
                          'supplier', 'contract_number', 'faktura', 'comment')
    ordering_fields    = ('expected_date', 'created_at', 'status')
    http_method_names  = ('get', 'post', 'patch', 'head', 'options')

    @extend_schema(
        summary="Bir vaqtda bir nechta mahsulot uchun zakaz (bulk)",
        description=(
            "Bir nechta mahsulotni birdan zakaz qilish (masalan buyurtmada "
            "yetishmagan bir necha mahsulot uchun). Har biri alohida Zakaz "
            "(status=new). Faol zakazi bor mahsulot rad etiladi.\n\n"
            "```json\n"
            "{\n"
            '  "supplier": "Xitoy, Guangzhou",\n'
            '  "expected_date": "2026-08-15",\n'
            '  "contract_number": "SH-2026/045",\n'
            '  "items": [\n'
            '    { "product": 12, "quantity": 7 },\n'
            '    { "product": 7,  "quantity": 5 }\n'
            "  ]\n"
            "}\n"
            "```"
        ),
        request=ZakazBulkCreateSerializer,
        tags=["Zakaz"],
    )
    @action(detail=False, methods=['post'])
    def bulk(self, request):
        serializer = ZakazBulkCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        zakazlar = serializer.save()
        return Response(
            ZakazBulkCreateSerializer().to_representation(zakazlar),
            status=201,
        )


# ── Mahsulot shartnomalari reestri ───────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        summary="Mahsulot shartnomalari reestri",
        description=(
            "MAHSULOTGA bog'langan barcha shartnomalar — har bir holat va "
            "detal (buyurtma yaratildi/tahrirlandi/yetkazildi, zakaz "
            "tasdiqlandi/yuborildi/qabul qilindi...) o'z shartnoma raqami va "
            "asosi bilan AVTOMATIK yozib boriladi. Davlat va mijozlar oldida "
            "asos sifatida ishlatiladi.\n\n"
            "Filtr: `?product=1`, `?contract_number=SH-2026/045`, "
            "`?source_type=zakaz_ordered`, `?order=5`, `?zakaz=3`"
        ),
        tags=["Shartnomalar reestri"],
    ),
    retrieve=extend_schema(summary="Bitta reestr yozuvi",
                           tags=["Shartnomalar reestri"]),
)
class ProductContractViewSet(ListModelMixin, RetrieveModelMixin,
                             GenericViewSet):
    """
    Shartnomalar reestri — faqat o'qish uchun.
    Yozuvlar tizim tomonidan avtomatik yaratiladi, qo'lda
    o'zgartirilmaydi/o'chirilmaydi (audit butunligi).
    """
    queryset           = (ProductContract.objects
                          .select_related('product', 'order', 'zakaz',
                                          'created_by'))
    serializer_class   = ProductContractSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields   = ('product', 'contract_number', 'source_type',
                          'order', 'zakaz', 'contract_date')
    search_fields      = ('contract_number', 'faktura', 'asos',
                          'product__name', 'product__serial_number')
    ordering_fields    = ('created_at', 'contract_date')
