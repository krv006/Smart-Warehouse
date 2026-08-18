import json
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import (ModelSerializer, Serializer,
                                        SerializerMethodField, ReadOnlyField,
                                        ValidationError, BooleanField,
                                        CharField, DateField,
                                        DecimalField, IntegerField,
                                        PrimaryKeyRelatedField, FileField,
                                        UUIDField)

from apps.clients.models import Client
from apps.orders.dates import current_year_end
from apps.orders.models import (Order, OrderItem, OrderHistory,
                                Zakaz, ZakazHistory,
                                ProductContract, register_contract,
                                allocate_pending_orders, build_contract_number)
from apps.warehouse.models import Category, Product

# Buyurtma sarlavha tahririda kuzatiladigan maydonlar (tarixga yoziladi)
_ORDER_TRACKED_FIELDS = ('client', 'prepaid_amount', 'contract_number',
                         'contract_date', 'due_date', 'comment')

_ZAKAZ_TRACKED_FIELDS = ('quantity', 'received_qty', 'supplier',
                         'contract_number', 'contract_date', 'asos', 'faktura',
                         'expected_date', 'warehouse_location', 'comment')


def _can_manage_prices(user):
    return bool(getattr(user, 'is_management', False)
                or getattr(user, 'is_superuser', False))


def _can_manage_payment(user):
    """Import to'lov holati — Management yoki Buxgalter."""
    return _can_manage_prices(user) or bool(getattr(user, 'is_accountant', False))


def _can_view_prices(user):
    return _can_manage_prices(user) or bool(getattr(user, 'is_accountant', False))


def _sync_product_import_prices(product, data):
    """Import qatoridagi kelish/ketish narxini ombordagi mahsulotga yozadi."""
    updates = {}
    if data.get('unit_price') not in (None, ''):
        updates['purchase_price'] = data['unit_price']
    if data.get('selling_price') not in (None, ''):
        updates['selling_price'] = data['selling_price']
    if data.get('delivery_price') not in (None, ''):
        updates['delivery_price'] = data['delivery_price']
    if data.get('vat_percent'):
        updates['vat_percent'] = data['vat_percent']
    if not updates:
        return product
    for field, value in updates.items():
        setattr(product, field, value)
    product.save(update_fields=list(updates))
    return product


def _strip_zakaz_payment_fields(attrs):
    attrs.pop('currency', None)
    attrs.pop('payment_status', None)
    attrs.pop('paid_amount', None)


def _validate_partial_paid_amount(payment_status, paid_amount, total, *, require_total=False):
    if payment_status != Zakaz.PARTIAL:
        return
    if paid_amount in (None, '') or Decimal(str(paid_amount or 0)) <= 0:
        raise ValidationError({
            'paid_amount': 'Qisman to\'lov uchun to\'langan miqdorni kiriting.'})
    if require_total and (total is None or total <= 0):
        raise ValidationError({
            'paid_amount': 'Qisman to\'lov uchun avval narx (unit_price) kiritilishi kerak.'})
    if total is not None and total > 0 and Decimal(str(paid_amount)) > total:
        raise ValidationError({
            'paid_amount': (
                f'To\'langan summa jami import summasidan ({total}) oshmasligi kerak.')})


def _split_partial_payment(paid_amount, line_totals):
    """Qisman to'lovni qatorlar bo'yicha taqsimlash; qoldiq oxirgi qatorga."""
    if not line_totals:
        return []
    grand_total = sum(line_totals, Decimal('0'))
    if grand_total <= 0:
        return [Decimal('0')] * len(line_totals)
    total_paid = Decimal(str(paid_amount))
    splits = []
    allocated = Decimal('0')
    last_idx = len(line_totals) - 1
    for idx, line_total in enumerate(line_totals):
        if idx == last_idx:
            line_paid = (total_paid - allocated).quantize(Decimal('0.01'))
        else:
            line_paid = (total_paid * line_total / grand_total).quantize(Decimal('0.01'))
            allocated += line_paid
        splits.append(line_paid)
    return splits


def order_serializer_class(user):
    if user and user.is_authenticated and (
            getattr(user, 'is_management', False)
            or getattr(user, 'is_accountant', False)
            or getattr(user, 'is_superuser', False)):
        return OrderSerializer
    return OrderOperatorSerializer


def zakaz_serializer_class(user):
    if user and user.is_authenticated and (
            getattr(user, 'is_management', False)
            or getattr(user, 'is_accountant', False)
            or getattr(user, 'is_superuser', False)):
        return ZakazSerializer
    return ZakazOperatorSerializer


def _fill_operator_item_prices(items_data):
    """
    Narx kirita olmaydigan foydalanuvchi (Operator) uchun qator narxini
    boshqaradi: YANGI qator — mahsulotning belgilangan sotuv narxidan
    (`Product.selling_price`) avtomatik oladi (Sale bilan bir xil qoida —
    aks holda buyurtma narxsiz qolib, kassaga (Payment) UMUMAN tushmay
    qolardi, chunki `Order.total` `None` bo'lib qoladi). MAVJUD qatorni
    operator narxini o'zgartira olmaydi — shu maydon chetlab o'tiladi
    (eski narx saqlanadi).
    """
    if not items_data:
        return items_data
    for item in items_data:
        is_new = not item.get('id')
        if is_new:
            product = item.get('product')
            item['unit_price'] = (product.selling_price if product else None) or 0
        else:
            item.pop('unit_price', None)
    return items_data


def _diff(instance, validated_data, fields):
    """Eski → yangi qiymatlar lug'ati (faqat o'zgarganlar)."""
    changes = {}
    for f in fields:
        if f not in validated_data:
            continue
        old = getattr(instance, f)
        new = validated_data[f]
        if old != new:
            changes[f] = {'old': str(old) if old is not None else None,
                          'new': str(new) if new is not None else None}
    return changes


# ── Order tarixi ──────────────────────────────────────────────────────────────

class OrderHistorySerializer(ModelSerializer):
    changed_by_name = SerializerMethodField()
    action_display  = SerializerMethodField()

    class Meta:
        model  = OrderHistory
        fields = ('id', 'action', 'action_display', 'contract_number', 'faktura',
                  'asos', 'changes', 'changed_by', 'changed_by_name', 'created_at')

    def get_changed_by_name(self, obj):
        return str(obj.changed_by) if obj.changed_by else None

    def get_action_display(self, obj):
        return obj.get_action_display()


# ── Order (Bron) — BITTA buyurtma, ko'p mahsulot ─────────────────────────────

class OrderItemSerializer(ModelSerializer):
    """Buyurtma ichidagi bitta mahsulot qatori."""
    id               = IntegerField(required=False,
                                    help_text='Tahrirda mavjud qatorni ko\'rsatish uchun')
    remove           = BooleanField(write_only=True, required=False, default=False,
                                    help_text='True — qatorni buyurtmadan olib tashlash (id bilan)')
    product          = PrimaryKeyRelatedField(queryset=Product.objects.all(),
                                              required=False)
    quantity         = IntegerField(required=False, min_value=1)
    product_name     = SerializerMethodField()
    total            = ReadOnlyField()
    backorder_qty    = ReadOnlyField()
    has_active_zakaz = ReadOnlyField()

    class Meta:
        model  = OrderItem
        fields = ('id', 'remove', 'product', 'product_name',
                  'quantity', 'unit_price', 'total',
                  'reserved_qty', 'backorder_qty', 'has_active_zakaz',
                  'comment')
        read_only_fields = ('reserved_qty',)
        extra_kwargs = {'unit_price': {'min_value': 0}}

    def get_product_name(self, obj):
        return str(obj.product)

    def validate(self, attrs):
        # O'chirishda id shart; boshqa holatlarda product+quantity kerak
        # (mavjud qator tahririda id bo'ladi — u yerda ham shart emas)
        if attrs.get('remove') and not attrs.get('id'):
            raise ValidationError('Qatorni o\'chirish uchun "id" kiritilishi shart.')
        if (not attrs.get('remove') and not attrs.get('id')
                and (not attrs.get('product') or not attrs.get('quantity'))):
            raise ValidationError(
                'Yangi qator uchun "product" va "quantity" kiritilishi shart.')
        return attrs


class OrderSerializer(ModelSerializer):
    """
    Buyurtma — BITTA hujjat, ichida bir nechta mahsulot (`items`).
    Nechta mahsulot bo'lishidan qat'i nazar buyurtma bitta bo'ladi.
    """
    items            = OrderItemSerializer(many=True, required=False)
    client_name      = SerializerMethodField()
    total_quantity   = ReadOnlyField()
    reserved_qty     = ReadOnlyField()
    backorder_qty    = ReadOnlyField()
    total            = ReadOnlyField()
    balance_due      = ReadOnlyField()
    has_active_zakaz = ReadOnlyField()
    history          = OrderHistorySerializer(many=True, read_only=True)

    # Shartnoma raqami — agar yuborilmasa avtomatik yaratiladi
    contract_number = CharField(max_length=100, required=False, allow_blank=True)
    contract_date   = DateField(required=False)

    # Tahrir asosi — modelda saqlanmaydi, tarixga yoziladi
    asos = CharField(write_only=True, required=False, allow_blank=True,
                     help_text='Tahrir/amal asosi (tahrirlashda majburiy)')

    # Eski (bitta mahsulotli) format ham qabul qilinadi — items ga aylanadi
    product    = PrimaryKeyRelatedField(queryset=Product.objects.all(),
                                        required=False, write_only=True)
    quantity   = IntegerField(required=False, min_value=1, write_only=True)
    unit_price = DecimalField(max_digits=14, decimal_places=2, min_value=0,
                              required=False, allow_null=True, write_only=True)

    class Meta:
        model  = Order
        fields = (
            'id', 'client', 'client_name',
            'items',
            'product', 'quantity', 'unit_price',   # legacy (write-only)
            'total_quantity', 'total',
            'prepaid_amount', 'balance_due',
            'contract_number', 'contract_date', 'contract_file',
            'reserved_qty', 'backorder_qty',
            'has_active_zakaz',
            'due_date', 'status', 'comment', 'created_at',
            'asos', 'history',
        )
        read_only_fields = ('status', 'created_at')
        extra_kwargs = {'prepaid_amount': {'min_value': 0}}

    def get_client_name(self, obj):
        return str(obj.client) if obj.client else None

    def validate(self, attrs):
        # Yetkazish muddati — faqat joriy yil 31-dekabr
        year_end = current_year_end()
        if 'due_date' in attrs and attrs.get('due_date') and attrs['due_date'] != year_end:
            raise ValidationError({
                'due_date': f'Yetkazish muddati faqat {year_end.isoformat()} bo\'lishi kerak.',
            })
        if self.instance is None and 'due_date' not in attrs:
            attrs['due_date'] = year_end

        # Shartnoma raqami erkin matn — xodim istagan ko'rinishda qo'lda
        # kiritishi mumkin (masalan "412412412"), format tekshirilmaydi.
        # Bo'sh bo'lsa raqam create() ichida band qilinadi — validatsiya
        # muvaffaqiyatsiz tugasa raqam behuda sarflanmasin.
        # Tahrirlashda asos MAJBURIY — auditda "nima uchun" aniq bo'lishi kerak
        if self.instance is not None:
            if not attrs.get('asos'):
                raise ValidationError(
                    {'asos': 'Tahrirlash uchun asos kiritilishi shart.'})
            if self.instance.status in (Order.FULFILLED, Order.CANCELLED):
                raise ValidationError(
                    f'"{self.instance.get_status_display()}" holatidagi '
                    f'buyurtmani tahrirlab bo\'lmaydi.')
        else:
            # Yaratishda kamida bitta mahsulot bo'lishi shart
            if not attrs.get('items') and not attrs.get('product'):
                raise ValidationError(
                    {'items': 'Kamida bitta mahsulot kiritilishi kerak.'})

        # Oldindan to'lov jami summadan oshmasin (yaratishda; tahrirda
        # qatorlar qo'llangandan keyin update() ichida tekshiriladi)
        if self.instance is None:
            prepaid = attrs.get('prepaid_amount') or 0
            if prepaid:
                totals = []
                if attrs.get('items'):
                    totals = [i['quantity'] * i['unit_price']
                              for i in attrs['items'] if i.get('unit_price')]
                elif attrs.get('product') and attrs.get('unit_price'):
                    totals = [attrs.get('quantity', 1) * attrs['unit_price']]
                if totals and prepaid > sum(totals):
                    raise ValidationError({
                        'prepaid_amount': 'Oldindan to\'lov jami summadan oshib ketdi.'})
        return attrs

    # Eslatma: buyurtma (Order) HAR DOIM yaratiladi.
    # Qoldiq yetmasa — backorder bo'lib qoladi va yetishmagan qatorlar uchun
    # AVTOMATIK Zakaz ochiladi (o'sha shartnoma raqami asosida).

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('asos', None)
        validated_data.setdefault('contract_date', timezone.localdate())
        if not (validated_data.get('contract_number') or '').strip():
            validated_data['contract_number'] = build_contract_number(
                client=validated_data.get('client'),
                contract_date=validated_data.get('contract_date'),
            )
        user = self.context['request'].user

        # items yoki legacy (product/quantity/unit_price)
        items_data = validated_data.pop('items', None)
        product    = validated_data.pop('product', None)
        quantity   = validated_data.pop('quantity', None)
        unit_price = validated_data.pop('unit_price', None)
        can_manage_prices = _can_manage_prices(user)
        if not can_manage_prices:
            validated_data['prepaid_amount'] = 0
            # Operator narx kirita olmaydi — mahsulotning belgilangan sotuv
            # narxidan avtomatik olinadi (Sale bilan bir xil qoida), aks
            # holda buyurtma summasiz qolib kassaga umuman tushmay qolardi
            unit_price = (product.selling_price if product else None) or 0
        if not items_data:
            items_data = [{'product': product, 'quantity': quantity or 1,
                           'unit_price': unit_price}]
        elif not can_manage_prices:
            items_data = _fill_operator_item_prices(items_data)

        order = Order.objects.create(**validated_data)
        for item in items_data:
            item.pop('id', None)
            item.pop('remove', None)
            OrderItem.objects.create(order=order, **item)

        order.reserve()

        # Tarix: yaratildi (shartnoma raqami + aniq sana/vaqt)
        names = ', '.join(i.product.name for i in order.items.all())
        asos_text = (f'Buyurtma yaratildi ({names}) — '
                     f'shartnoma №{order.contract_number}.')
        OrderHistory.objects.create(
            order=order, changed_by=user, action=OrderHistory.CREATED,
            contract_number=order.contract_number,
            asos=asos_text,
        )
        # MAHSULOT shartnomalar reestriga — har qator mahsuloti uchun
        for item in order.items.all():
            register_contract(
                item.product, ProductContract.ORDER_CREATED,
                contract_number=order.contract_number,
                contract_date=order.contract_date,
                asos=asos_text, order=order, user=user,
            )

        # Pul (summa + oldindan to'lov) bitta amalda KASSAGA tushadi
        order.sync_payment(user=user)

        # 2-etap: yetishmagan qatorlar avtomatik Zakazga o'tadi
        order.create_backorder_zakaz(user=user)
        return order

    @transaction.atomic
    def update(self, instance, validated_data):
        asos = validated_data.pop('asos', '')
        user = self.context['request'].user

        items_data   = validated_data.pop('items', None)
        legacy_qty   = validated_data.pop('quantity', None)
        legacy_price = validated_data.pop('unit_price', None)
        validated_data.pop('product', None)
        if not _can_manage_prices(user):
            # Operator mavjud (legacy, bitta qatorli) buyurtmaning narxini
            # o'zgartira olmaydi — eski narx saqlanadi
            legacy_price = None
            if items_data:
                items_data = _fill_operator_item_prices(items_data)

        changes = _diff(instance, validated_data, _ORDER_TRACKED_FIELDS)

        order = super().update(instance, validated_data)

        # Qatorlarni yangilash: id bor → mavjud qator, id yo'q → yangi qator,
        # remove=true → qatorni olib tashlash (mijoz fikri o'zgarishi mumkin)
        item_changes = []

        # Legacy: bitta qatorli buyurtmada quantity/unit_price to'g'ridan-to'g'ri
        if (not items_data and (legacy_qty is not None or legacy_price is not None)
                and order.items.count() == 1):
            item    = order.items.first()
            old_qty = item.quantity
            if legacy_qty is not None:
                item.quantity = legacy_qty
            if legacy_price is not None:
                item.unit_price = legacy_price
            item.save()
            if item.quantity != old_qty:
                item.resync_reservation()
                item_changes.append(
                    {'item': item.pk, 'product': str(item.product),
                     'quantity': {'old': old_qty, 'new': item.quantity}})
        if items_data:
            for d in items_data:
                iid    = d.pop('id', None)
                remove = d.pop('remove', False)

                if remove:
                    try:
                        item = order.items.get(pk=iid)
                    except OrderItem.DoesNotExist:
                        raise ValidationError(
                            {'items': f'Qator #{iid} bu buyurtmada topilmadi.'})
                    if order.items.count() <= 1:
                        raise ValidationError(
                            {'items': 'Oxirgi qatorni o\'chirib bo\'lmaydi — '
                                      'butun buyurtmani bekor qilish uchun '
                                      '/cancel/ dan foydalaning.'})
                    # Bron bo'shatiladi va boshqa kutayotganlarga taqsimlanadi
                    product = item.product
                    item.release()
                    item_changes.append(
                        {'item': iid, 'product': str(product),
                         'removed': item.quantity})
                    item.delete()
                    allocate_pending_orders(product)
                    continue

                if iid:
                    try:
                        item = order.items.get(pk=iid)
                    except OrderItem.DoesNotExist:
                        raise ValidationError(
                            {'items': f'Qator #{iid} bu buyurtmada topilmadi.'})
                    old_qty = item.quantity
                    for f in ('quantity', 'unit_price', 'comment'):
                        if f in d:
                            setattr(item, f, d[f])
                    item.save()
                    if item.quantity != old_qty:
                        item.resync_reservation()
                        item_changes.append(
                            {'item': iid, 'product': str(item.product),
                             'quantity': {'old': old_qty, 'new': item.quantity}})
                else:
                    d.pop('reserved_qty', None)
                    item = OrderItem.objects.create(order=order, **d)
                    item.reserve()
                    item_changes.append(
                        {'item': item.pk, 'product': str(item.product),
                         'added': item.quantity})
        if item_changes:
            changes['items'] = item_changes

        # Qatorlar o'zgargach eski (prefetch) keshni tozalaymiz — total,
        # holat va kassa YANGI qatorlardan qayta hisoblanishi uchun.
        order._prefetched_objects_cache = {}

        order.refresh_status()

        # Oldindan to'lov jami summadan oshmasin (qatorlar qo'llanganidan keyin)
        if (order.total is not None
                and (order.prepaid_amount or 0) > order.total):
            raise ValidationError({
                'prepaid_amount': (
                    f'Oldindan to\'lov ({order.prepaid_amount}) yangi jami '
                    f'summadan ({order.total}) oshib ketdi — shu so\'rovda '
                    f'`prepaid_amount` ni ham kamaytiring (qaytarilgan pul '
                    f'kassada korrektsiya bo\'lib yoziladi).')})

        # Kassa yozuvini yangilash (summa/oldindan to'lov o'zgargan bo'lishi
        # mumkin — farq alohida tranzaksiya bo'lib yoziladi)
        order.sync_payment(user=user)

        # Zakaz miqdorini yetishmovchilikка moslash (oshsa "yana qo'shildi",
        # kamaysa kamayadi, kerak bo'lmasa bekor / yangi ochiladi)
        order.sync_backorder_zakaz(user=user)

        # Tarix: har bir tahrir shartnoma raqami + asos + sana/vaqt bilan
        OrderHistory.objects.create(
            order=order, changed_by=user, action=OrderHistory.EDITED,
            contract_number=order.contract_number,
            asos=asos,
            changes=json.dumps(changes, ensure_ascii=False) if changes else None,
        )
        # Reestr: tahrir har qator mahsulotiga yoziladi
        for item in order.items.all():
            register_contract(
                item.product, ProductContract.ORDER_EDITED,
                contract_number=order.contract_number,
                contract_date=order.contract_date,
                asos=asos, order=order, user=user,
            )
        return order


class OrderItemOperatorSerializer(OrderItemSerializer):
    """Operator uchun — narx va summa yashirin."""

    class Meta(OrderItemSerializer.Meta):
        fields = ('id', 'remove', 'product', 'product_name',
                  'quantity', 'reserved_qty', 'backorder_qty',
                  'has_active_zakaz', 'comment')


class OrderOperatorSerializer(OrderSerializer):
    """Operator uchun — moliyaviy maydonlar yashirin."""
    items = OrderItemOperatorSerializer(many=True, required=False)

    class Meta(OrderSerializer.Meta):
        fields = (
            'id', 'client', 'client_name',
            'items',
            'total_quantity',
            'contract_number', 'contract_date', 'contract_file',
            'reserved_qty', 'backorder_qty',
            'has_active_zakaz',
            'due_date', 'status', 'comment', 'created_at',
            'asos', 'history',
        )


class OrderBulkCreateSerializer(Serializer):
    """
    Bir vaqtda bir nechta mahsulot buyurtmasi — natija BITTA buyurtma,
    ichida bir nechta qator (items).

    Namuna:
    {
      "client": "<uuid>",
      "due_date": "2026-08-01",
      "contract_number": "SH-2026/045",
      "prepaid_amount": "5000000",
      "items": [
        { "product": 12, "quantity": 4, "unit_price": "3900000" },
        { "product": 7,  "quantity": 2, "unit_price": "1200000" }
      ]
    }
    """
    client          = PrimaryKeyRelatedField(queryset=Client.objects.all(),
                                             required=False, allow_null=True)
    due_date        = DateField(required=False, allow_null=True)
    contract_number = CharField(max_length=100, required=False, allow_blank=True)
    contract_date   = DateField(required=False)
    contract_file   = FileField(required=False, allow_null=True)
    prepaid_amount  = DecimalField(max_digits=14, decimal_places=2, min_value=0,
                                   required=False, allow_null=True)
    comment         = CharField(required=False, allow_blank=True, allow_null=True)
    items           = OrderItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise ValidationError('Kamida bitta mahsulot kiritilishi kerak.')
        return value

    def create(self, validated_data):
        # BITTA buyurtma sifatida OrderSerializer orqali yaratiladi
        if validated_data.get('prepaid_amount') is None:
            validated_data.pop('prepaid_amount', None)
        return OrderSerializer(context=self.context).create(validated_data)

    def to_representation(self, instance):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        serializer_class = order_serializer_class(user)
        return {'order': serializer_class(instance, context=self.context).data}


# ── Mahsulot shartnomalari reestri ───────────────────────────────────────────

class ProductContractSerializer(ModelSerializer):
    product_name        = SerializerMethodField()
    source_type_display = SerializerMethodField()
    created_by_name     = SerializerMethodField()

    class Meta:
        model  = ProductContract
        fields = ('id', 'product', 'product_name',
                  'contract_number', 'contract_date',
                  'asos', 'faktura',
                  'source_type', 'source_type_display',
                  'order', 'zakaz', 'invoice',
                  'created_by', 'created_by_name', 'created_at')

    def get_product_name(self, obj):
        return str(obj.product)

    def get_source_type_display(self, obj):
        return obj.get_source_type_display()

    def get_created_by_name(self, obj):
        return str(obj.created_by) if obj.created_by else None


# ── Zakaz tarixi ──────────────────────────────────────────────────────────────

class ZakazHistorySerializer(ModelSerializer):
    changed_by_name = SerializerMethodField()
    action_display  = SerializerMethodField()

    class Meta:
        model  = ZakazHistory
        fields = ('id', 'action', 'action_display', 'old_status', 'new_status',
                  'contract_number', 'contract_date', 'asos', 'faktura',
                  'changes', 'changed_by', 'changed_by_name', 'created_at')

    def get_changed_by_name(self, obj):
        return str(obj.changed_by) if obj.changed_by else None

    def get_action_display(self, obj):
        return obj.get_action_display()


# ── Zakaz (Etkazuvchidan buyurtma) ────────────────────────────────────────────

class ZakazInlineProductSerializer(Serializer):
    """Importda qo'lda kiritilgan mahsulot — zakaz yaratishda omborga qo'shiladi."""
    name = CharField(max_length=255)

    # Kategoriya — import qatoridan yaratiladigan mahsulot uchun MAJBURIY
    category = PrimaryKeyRelatedField(queryset=Category.objects.all())
    serial_number = CharField(required=False, allow_blank=True, default='')
    barcode = CharField(required=False, allow_blank=True, allow_null=True)
    unit = CharField(required=False, default='piece')
    vat_percent = CharField(required=False, allow_blank=True, default='none')
    purchase_price = DecimalField(max_digits=14, decimal_places=2,
                                  required=False, allow_null=True)
    selling_price = DecimalField(max_digits=14, decimal_places=2,
                                 required=False, allow_null=True)
    delivery_price = DecimalField(max_digits=14, decimal_places=2,
                                  required=False, allow_null=True)

    def validate_serial_number(self, value):
        """Seriya raqami noyob — band bo'lsa 500 emas, tushunarli 400 qaytadi."""
        from apps.warehouse.product_utils import (normalize_product_serial,
                                                  serial_number_is_taken)
        serial = normalize_product_serial(value)
        if serial and serial_number_is_taken(serial):
            raise ValidationError(
                f'"{serial}" seriya raqami omborda allaqachon mavjud. '
                f'Ombordagi mahsulotni tanlang yoki boshqa raqam kiriting.')
        return value


class ZakazSerializer(ModelSerializer):
    new_product = ZakazInlineProductSerializer(required=False, write_only=True)
    product_name        = SerializerMethodField()
    created_by_name     = SerializerMethodField()
    status_display      = SerializerMethodField()
    type_display        = SerializerMethodField()
    payment_status_display = SerializerMethodField()
    total               = ReadOnlyField()   # unit_price × quantity (avtomatik)
    vat_amount          = ReadOnlyField()   # QQS — kelish narxi asosida
    total_with_vat      = ReadOnlyField()
    order_contract      = SerializerMethodField()
    warehouse_location  = CharField(required=False, allow_null=True,
                                    allow_blank=True, max_length=255)
    history             = ZakazHistorySerializer(many=True, read_only=True)

    class Meta:
        model  = Zakaz
        fields = (
            'id', 'zakaz_type', 'type_display', 'order', 'order_contract',
            'product', 'product_name', 'new_product',
            'quantity', 'received_qty',
            'unit_price', 'selling_price', 'delivery_price',
            'vat_percent', 'vat_amount', 'total_with_vat',
            'currency', 'total',
            'payment_status', 'payment_status_display', 'paid_amount',
            'supplier', 'status', 'status_display',
            'contract_number', 'contract_date', 'confirmed_at',
            'asos', 'faktura',
            'expected_date', 'warehouse_location',
            'created_by', 'created_by_name',
            'comment', 'created_at',
            'import_batch',
            'history',
        )
        # zakaz_type/order — yaratishda o'rnatiladi, keyin o'zgarmaydi (audit;
        # order'ni ko'chirish buyurtma↔zakaz bog'lanishini buzadi)
        read_only_fields = ('created_by', 'confirmed_at', 'created_at',
                            'zakaz_type', 'order')
        extra_kwargs = {'product': {'required': False, 'allow_null': True}}

    def get_product_name(self, obj):
        # Import ro'yxatida faqat mahsulot nomi — seriya raqamisiz
        return obj.product.name if obj.product else None

    def get_created_by_name(self, obj):
        return str(obj.created_by) if obj.created_by else None

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_type_display(self, obj):
        return obj.get_zakaz_type_display()

    def get_payment_status_display(self, obj):
        return obj.get_payment_status_display()

    def get_order_contract(self, obj):
        """Manba buyurtmaning shartnoma raqami (asos zanjiri)."""
        if obj.order_id:
            return {'order': obj.order_id,
                    'contract_number': obj.order.contract_number,
                    'contract_date': str(obj.order.contract_date)}
        return None

    # Operator uchun taqiq: received_qty (ombor hisobiga ta'sir qiladi) —
    # faqat Management. Backorder zakazda miqdor/mahsulot buyurtmadan
    # keladi — operator qo'lda o'zgartira olmaydi.
    _MANAGEMENT_ONLY_FIELDS = frozenset(('received_qty',))
    _BACKORDER_LOCKED_FIELDS = frozenset(('quantity', 'product', 'unit_price'))

    def validate_unit_price(self, value):
        if value is not None and value < 0:
            raise ValidationError('Narx manfiy bo\'lishi mumkin emas.')
        return value

    def _create_inline_product(self, data):
        from apps.warehouse.product_utils import create_import_product
        return create_import_product(data)

    def validate(self, attrs):
        # Yaratish: mustaqil (manual) import uchun narx faqat Management kiritadi.
        user = self.context['request'].user
        if self.instance is None:
            new_product = attrs.pop('new_product', None)
            product = attrs.get('product')
            if not product and not new_product:
                raise ValidationError({
                    'product': 'Mahsulotni tanlang yoki qo\'lda kiriting.',
                })
            if product and new_product:
                raise ValidationError(
                    'Mahsulotni tanlash va qo\'lda kiritish bir vaqtda bo\'lmaydi.')
            if new_product:
                if not _can_manage_prices(user):
                    new_product = dict(new_product)
                    new_product.pop('purchase_price', None)
                    new_product.pop('selling_price', None)
                    new_product.pop('delivery_price', None)
                attrs['_new_product_data'] = new_product
            if _can_manage_prices(user):
                if attrs.get('unit_price') in (None, ''):
                    raise ValidationError({
                        'unit_price': 'Mustaqil import uchun kelish narxi '
                                      '(unit_price) kiritilishi shart.'})
                if attrs.get('selling_price') in (None, ''):
                    raise ValidationError({
                        'selling_price': 'Mustaqil import uchun ketish narxi '
                                         '(selling_price) kiritilishi shart.'})
            else:
                attrs.pop('unit_price', None)
                attrs.pop('selling_price', None)
                attrs.pop('delivery_price', None)
                if not _can_manage_payment(user):
                    _strip_zakaz_payment_fields(attrs)
        else:
            # Qabul qilingan/bekor qilingan zakazda miqdor va narx qotib qoladi
            locked = self.instance.status in (Zakaz.RECEIVED, Zakaz.CANCELLED)
            if locked and ('quantity' in attrs or 'unit_price' in attrs):
                raise ValidationError(
                    f'"{self.instance.get_status_display()}" holatidagi zakazda '
                    f'miqdor yoki narxni o\'zgartirib bo\'lmaydi.')

            # Rol chegarasi: received_qty faqat Management (ombor hisobi);
            # backorder zakazda miqdor/mahsulot buyurtmadan keladi
            user = self.context['request'].user
            if not getattr(user, 'is_management', False):
                blocked = set(attrs) & self._MANAGEMENT_ONLY_FIELDS
                if self.instance.is_backorder:
                    blocked |= set(attrs) & self._BACKORDER_LOCKED_FIELDS
                if blocked:
                    raise PermissionDenied(
                        'Bu maydonlarni faqat boshqaruv (Management) '
                        f'o\'zgartira oladi: {", ".join(sorted(blocked))}.')

        # Qabul miqdori zakaz miqdoridan oshmasligi kerak — aks holda omborga
        # "fantom" tovar kiradi
        quantity = attrs.get(
            'quantity', getattr(self.instance, 'quantity', None))
        received = attrs.get(
            'received_qty', getattr(self.instance, 'received_qty', 0) or 0)
        if quantity is not None and received and received > quantity:
            raise ValidationError({
                'received_qty': (f'Qabul qilingan miqdor ({received}) zakaz '
                                 f'miqdoridan ({quantity}) oshib ketmasligi kerak.')})

        payment_status = attrs.get(
            'payment_status',
            getattr(self.instance, 'payment_status', None) if self.instance else Zakaz.UNPAID,
        )
        paid_amount = attrs.get(
            'paid_amount',
            getattr(self.instance, 'paid_amount', None) if self.instance else None,
        )
        # To'lov maydonlari tegilmagan tahrirda (masalan faqat izoh) eski
        # yozuvni bloklamaymiz — lekin miqdor/narx o'zgarsa jami summa ham
        # o'zgaradi, shuning uchun ularni ham "tegilgan" deb hisoblaymiz —
        # aks holda miqdorni kamaytirish paid_amount > total holatini
        # tekshirilmasdan qoldiradi
        payment_touched = ('payment_status' in attrs or 'paid_amount' in attrs
                           or 'quantity' in attrs or 'unit_price' in attrs
                           or self.instance is None)
        if payment_status == Zakaz.PARTIAL and payment_touched:
            line_total = None
            if self.instance:
                qty = attrs.get('quantity', self.instance.quantity)
                unit_price = attrs.get('unit_price', self.instance.unit_price)
                if unit_price is not None and qty:
                    line_total = Decimal(str(unit_price)) * Decimal(str(qty))
            elif attrs.get('unit_price') is not None and attrs.get('quantity'):
                line_total = (Decimal(str(attrs['unit_price']))
                              * Decimal(str(attrs['quantity'])))
            # Narx noma'lum bo'lsa qisman to'lovni tekshirib bo'lmaydi —
            # summa jami importdan oshib ketishi mumkin, shuning uchun taqiq
            _validate_partial_paid_amount(
                payment_status, paid_amount, line_total, require_total=True)
        elif payment_status == Zakaz.UNPAID:
            attrs['paid_amount'] = Decimal('0')
        elif payment_status == Zakaz.PAID:
            qty = attrs.get(
                'quantity',
                getattr(self.instance, 'quantity', None) if self.instance else None,
            )
            unit_price = attrs.get(
                'unit_price',
                getattr(self.instance, 'unit_price', None) if self.instance else None,
            )
            if unit_price is not None and qty:
                attrs['paid_amount'] = Decimal(str(unit_price)) * Decimal(str(qty))

        return attrs

    def create(self, validated_data):
        from apps.common.contracts import allocate_contract_number

        # Status har doim 'new' dan boshlanadi; API orqali — MUSTAQIL zakaz
        new_product_data = validated_data.pop('_new_product_data', None)
        if new_product_data:
            new_product_data = dict(new_product_data)
            new_product_data.setdefault('purchase_price',
                                        validated_data.get('unit_price'))
            new_product_data.setdefault('selling_price',
                                        validated_data.get('selling_price'))
            new_product_data.setdefault('delivery_price',
                                        validated_data.get('delivery_price'))
            if validated_data.get('vat_percent'):
                new_product_data.setdefault('vat_percent',
                                            validated_data['vat_percent'])
            validated_data['product'] = self._create_inline_product(new_product_data)
        elif validated_data.get('product'):
            _sync_product_import_prices(validated_data['product'], validated_data)
        if not (validated_data.get('contract_number') or '').strip():
            validated_data['contract_number'] = allocate_contract_number(
                validated_data.get('contract_date'))
        if not validated_data.get('import_batch'):
            validated_data['import_batch'] = uuid.uuid4()
        validated_data['status']     = Zakaz.NEW
        validated_data['zakaz_type'] = Zakaz.MANUAL
        validated_data['created_by'] = self.context['request'].user
        zakaz = super().create(validated_data)
        ZakazHistory.objects.create(
            zakaz=zakaz, changed_by=zakaz.created_by,
            action=ZakazHistory.CREATED, new_status=Zakaz.NEW,
            contract_number=zakaz.contract_number,
            contract_date=zakaz.contract_date,
            asos='Zakaz yaratildi.',
        )
        register_contract(
            zakaz.product, ProductContract.ZAKAZ_CREATED,
            contract_number=zakaz.contract_number,
            contract_date=zakaz.contract_date,
            asos='Zakaz yaratildi.', zakaz=zakaz, user=zakaz.created_by,
        )
        if zakaz.zakaz_type == Zakaz.MANUAL and zakaz.total:
            from apps.orders.zakaz_payment import sync_zakaz_expense
            sync_zakaz_expense(zakaz, user=zakaz.created_by)
        if zakaz.payment_status == Zakaz.PAID:
            zakaz.receive(user=zakaz.created_by)
        return zakaz

    # Har bir status o'zgarishi → reestrga qaysi turda yozilishi
    _CONTRACT_SOURCE = {
        Zakaz.CONFIRMED: ProductContract.ZAKAZ_CONFIRMED,
        Zakaz.ORDERED:   ProductContract.ZAKAZ_ORDERED,
        Zakaz.RECEIVED:  ProductContract.ZAKAZ_RECEIVED,
        Zakaz.CANCELLED: ProductContract.ZAKAZ_CANCELLED,
    }

    _STATUS_TRANSITIONS = {
        Zakaz.NEW:       (Zakaz.CONFIRMED, Zakaz.CANCELLED),
        Zakaz.CONFIRMED: (Zakaz.ORDERED, Zakaz.CANCELLED),
        Zakaz.ORDERED:   (Zakaz.RECEIVED, Zakaz.CANCELLED),
    }

    @transaction.atomic
    def update(self, instance, validated_data):
        # Atomic: status 'received' ga o'tib, receive() (ombor to'ldirish +
        # taqsimlash) yiqilsa — hammasi birga qaytariladi; zakaz RECEIVED'da
        # stock kirmagan holda qotib qolmaydi.
        validated_data.pop('import_batch', None)
        user       = self.context['request'].user
        new_status = validated_data.get('status')
        status_changing = bool(new_status and new_status != instance.status)

        # Status o'zgartirish — faqat Management
        if status_changing:
            if not getattr(user, 'is_management', False):
                raise PermissionDenied(
                    'Status faqat boshqaruv (Management) tomonidan o\'zgartirilishi mumkin.'
                )
            # Bekor qilingan yoki qabul qilingan zakazni o'zgartirib bo'lmaydi
            if instance.status in (Zakaz.RECEIVED, Zakaz.CANCELLED):
                raise ValidationError(
                    f'"{instance.get_status_display()}" statusidagi zakazni o\'zgartirib bo\'lmaydi.'
                )

            allowed = self._STATUS_TRANSITIONS.get(instance.status, ())
            if new_status not in allowed:
                raise ValidationError({
                    'status': (
                        f'"{instance.get_status_display()}" holatidan '
                        f'"{dict(Zakaz.STATUS_CHOICES).get(new_status, new_status)}" '
                        f'holatiga o\'tib bo\'lmaydi.'
                    ),
                })

            errors = {}

            # HAR BIR holat o'zgarishida ASOS majburiy (aynan shu o'tish uchun)
            if not validated_data.get('asos'):
                errors['asos'] = (f'"{dict(Zakaz.STATUS_CHOICES).get(new_status, new_status)}" '
                                  f'holatiga o\'tish uchun asos kiritilishi shart.')

            # HAR BIR ish holati (tasdiqlash/yuborish/qabul) uchun SHARTNOMA majburiy
            if new_status in (Zakaz.CONFIRMED, Zakaz.ORDERED, Zakaz.RECEIVED):
                contract = validated_data.get('contract_number') or instance.contract_number
                if not contract:
                    errors['contract_number'] = (
                        'Shartnoma (dogavor) raqami kiritilmaguncha bu holatga '
                        'o\'tkazib bo\'lmaydi.')

            # QABUL QILISH: qo'shimcha faktura majburiy
            if new_status == Zakaz.RECEIVED:
                faktura = validated_data.get('faktura') or instance.faktura
                if not faktura:
                    errors['faktura'] = 'Qabul qilish uchun faktura kiritilishi shart.'

            if errors:
                raise ValidationError(errors)

            # Sana: yangi shartnoma bo'lsa — bugungi kun (Tashkent);
            # buyurtmadan kelgan (eski) shartnoma bo'lsa — o'sha kun saqlanadi
            if new_status in (Zakaz.CONFIRMED, Zakaz.RECEIVED):
                if not (validated_data.get('contract_date') or instance.contract_date):
                    validated_data['contract_date'] = timezone.localdate()
            if new_status == Zakaz.CONFIRMED:
                validated_data['confirmed_at'] = timezone.now()

        old_status         = instance.status
        was_received       = instance.status == Zakaz.RECEIVED
        old_payment_status = instance.payment_status
        changes      = _diff(instance, validated_data, _ZAKAZ_TRACKED_FIELDS)

        zakaz = super().update(instance, validated_data)

        # Tarix: status o'zgarishi yoki oddiy tahrir — shartnoma + asos +
        # faktura + aniq sana/vaqt bilan
        if status_changing:
            action = (ZakazHistory.RECEIVED if zakaz.status == Zakaz.RECEIVED
                      else ZakazHistory.STATUS_CHANGED)
            ZakazHistory.objects.create(
                zakaz=zakaz, changed_by=user, action=action,
                old_status=old_status, new_status=zakaz.status,
                contract_number=zakaz.contract_number,
                contract_date=zakaz.contract_date,
                asos=zakaz.asos, faktura=zakaz.faktura,
                changes=json.dumps(changes, ensure_ascii=False) if changes else None,
            )
            # MAHSULOT shartnomalar reestriga avtomatik yozuv — har holat
            # o'z shartnoma raqami va asosi bilan saqlanadi
            source = self._CONTRACT_SOURCE.get(zakaz.status)
            if source:
                register_contract(
                    zakaz.product, source,
                    contract_number=zakaz.contract_number,
                    contract_date=zakaz.contract_date,
                    asos=zakaz.asos, faktura=zakaz.faktura,
                    order=zakaz.order, zakaz=zakaz, user=user,
                )
        elif changes:
            ZakazHistory.objects.create(
                zakaz=zakaz, changed_by=user, action=ZakazHistory.EDITED,
                contract_number=zakaz.contract_number,
                contract_date=zakaz.contract_date,
                asos=zakaz.asos, faktura=zakaz.faktura,
                changes=json.dumps(changes, ensure_ascii=False),
            )

        # Birinchi marta 'received' ga o'tganda ombor to'ldir + buyurtmalar
        # qismini yangilash (shartnoma asosida, tarix bilan)
        if zakaz.status == Zakaz.RECEIVED and not was_received:
            zakaz.receive(user=user)

        # To'lov holati "To'landi" ga o'tganda ham — rasmiy qabul (received)
        # bosqichidan o'tmagan bo'lsa ham — tovar omborga kiritiladi: manba
        # "Import"dan "Ombor"ga o'zgaradi, qoldiq ko'rinadi (receive() ichida
        # stock_credited bilan himoyalangan, ikki marta kiritilib qolmaydi).
        if zakaz.payment_status == Zakaz.PAID and old_payment_status != Zakaz.PAID:
            zakaz.receive(user=user)

        if zakaz.zakaz_type == Zakaz.MANUAL and zakaz.total:
            from apps.orders.zakaz_payment import sync_zakaz_expense
            sync_zakaz_expense(zakaz, user=user)

        return zakaz


class ZakazOperatorSerializer(ZakazSerializer):
    """Operator uchun — import narxi va to'lov holati yashirin."""

    class Meta(ZakazSerializer.Meta):
        fields = (
            'id', 'zakaz_type', 'type_display', 'order', 'order_contract',
            'product', 'product_name', 'new_product',
            'quantity', 'received_qty',
            'supplier', 'status', 'status_display',
            'contract_number', 'contract_date', 'confirmed_at',
            'asos', 'faktura',
            'expected_date', 'warehouse_location',
            'created_by', 'created_by_name',
            'comment', 'created_at',
            'import_batch',
            'history',
        )


class ZakazItemSerializer(Serializer):
    """Bulk zakaz ichidagi bitta mahsulot qatori (mustaqil zakaz)."""
    product       = PrimaryKeyRelatedField(queryset=Product.objects.all(),
                                           required=False, allow_null=True)
    new_product   = ZakazInlineProductSerializer(required=False)
    quantity      = IntegerField(min_value=1)
    unit_price    = DecimalField(max_digits=14, decimal_places=2,
                                 min_value=0, required=False, allow_null=True)
    selling_price = DecimalField(max_digits=14, decimal_places=2,
                                 min_value=0, required=False, allow_null=True)
    delivery_price = DecimalField(max_digits=14, decimal_places=2,
                                  min_value=0, required=False, allow_null=True)
    vat_percent   = CharField(required=False, allow_blank=True, allow_null=True)
    currency      = CharField(required=False, allow_blank=True, allow_null=True)
    supplier      = CharField(required=False, allow_blank=True, allow_null=True)
    expected_date = DateField(required=False, allow_null=True)
    comment       = CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        product = attrs.get('product')
        new_product = attrs.get('new_product')
        if not product and not new_product:
            raise ValidationError(
                'Mahsulotni tanlang yoki yangi mahsulot ma\'lumotlarini kiriting.')
        if product and new_product:
            raise ValidationError(
                'Mahsulotni tanlash va yangi mahsulot kiritish bir vaqtda bo\'lmaydi.')
        user = self.context['request'].user
        if _can_manage_prices(user):
            if attrs.get('unit_price') in (None, ''):
                raise ValidationError({
                    'unit_price': 'Import uchun kelish narxi (unit_price) '
                                  'kiritilishi shart.'})
            if attrs.get('selling_price') in (None, ''):
                raise ValidationError({
                    'selling_price': 'Import uchun ketish narxi (selling_price) '
                                     'kiritilishi shart.'})
        else:
            attrs.pop('unit_price', None)
            attrs.pop('selling_price', None)
            attrs.pop('delivery_price', None)
        if new_product and not _can_manage_prices(user):
            attrs['new_product'] = {
                k: v for k, v in new_product.items()
                if k not in ('purchase_price', 'selling_price', 'delivery_price')
            }
        return attrs


class ZakazBulkCreateSerializer(Serializer):
    """
    Bir vaqtda bir nechta mahsulot uchun zakaz.
    Har biri alohida Zakaz yozuvi bo'ladi (status="new").
    Har bir qatorda `product` (ombordan) yoki `new_product` (yangi) —
    qatorlar orasida aralash bo'lishi mumkin.

    Namuna:
    {
      "supplier": "Xitoy, Guangzhou",
      "expected_date": "2026-08-15",
      "contract_number": "SH-2026/045",
      "items": [
        { "product": 12, "quantity": 7 },
        { "new_product": { "name": "AMD CHIP", "unit": "piece" }, "quantity": 5 }
      ]
    }
    """
    supplier        = CharField(required=False, allow_blank=True, allow_null=True)
    expected_date   = DateField(required=False, allow_null=True)
    contract_number = CharField(required=False, allow_blank=True, allow_null=True)
    contract_date   = DateField(required=False, allow_null=True)
    currency        = CharField(required=False, allow_blank=True, allow_null=True)
    payment_status  = CharField(required=False, allow_blank=True, allow_null=True)
    paid_amount     = DecimalField(max_digits=14, decimal_places=2,
                                   required=False, allow_null=True)
    import_batch    = UUIDField(required=False, allow_null=True)
    items           = ZakazItemSerializer(many=True)

    def validate(self, attrs):
        user = self.context['request'].user
        items = attrs.get('items') or []
        if not _can_manage_payment(user):
            _strip_zakaz_payment_fields(attrs)
            payment_status = Zakaz.UNPAID
            attrs['paid_amount'] = Decimal('0')
        else:
            payment_status = attrs.get('payment_status') or Zakaz.UNPAID
            paid_amount = attrs.get('paid_amount')
            grand_total = sum(self._line_totals(items), Decimal('0'))
            if payment_status == Zakaz.PARTIAL:
                _validate_partial_paid_amount(
                    payment_status, paid_amount, grand_total, require_total=True)
            elif payment_status == Zakaz.UNPAID:
                attrs['paid_amount'] = Decimal('0')
        return attrs

    def validate_items(self, value):
        from apps.warehouse.product_utils import normalize_product_serial

        if not value:
            raise ValidationError('Kamida bitta mahsulot kiritilishi kerak.')
        errors = []
        seen_serials = {}
        for index, item in enumerate(value, start=1):
            # Bitta so'rov ichida bir xil seriya raqami — bazaga yozishda
            # unique cheklovi buziladi, shuning uchun oldindan to'xtatamiz
            new_product = item.get('new_product')
            if new_product:
                serial = normalize_product_serial(new_product.get('serial_number'))
                if serial:
                    if serial in seen_serials:
                        errors.append(
                            f'{index}-qator: "{serial}" seriya raqami '
                            f'{seen_serials[serial]}-qatorda ham ishlatilgan — '
                            f'seriya raqami takrorlanmasligi kerak.')
                    else:
                        seen_serials[serial] = index
        if errors:
            raise ValidationError(errors)
        return value

    def _line_totals(self, items):
        totals = []
        for item in items:
            price = item.get('unit_price')
            if price in (None, ''):
                totals.append(Decimal('0'))
            else:
                totals.append(Decimal(str(price)) * Decimal(str(item['quantity'])))
        return totals

    def create(self, validated_data):
        from apps.common.contracts import allocate_contract_number
        from apps.warehouse.product_utils import create_import_product

        common_supplier = validated_data.get('supplier')
        common_expected = validated_data.get('expected_date')
        contract_date   = validated_data.get('contract_date')
        contract_number = (validated_data.get('contract_number') or '').strip()
        if not contract_number:
            # Har kun uchun alohida o'suvchi tartib raqam: 1/1308, 2/1308, ...
            contract_number = allocate_contract_number(contract_date)
        currency        = validated_data.get('currency') or Zakaz.UZS
        payment_status  = validated_data.get('payment_status') or Zakaz.UNPAID
        paid_amount     = validated_data.get('paid_amount')
        items           = validated_data['items']
        user            = self.context['request'].user
        line_totals     = self._line_totals(items)
        grand_total     = sum(line_totals, Decimal('0'))
        batch_id        = validated_data.pop('import_batch', None) or uuid.uuid4()
        line_paid_splits = (
            _split_partial_payment(paid_amount, line_totals)
            if payment_status == Zakaz.PARTIAL and paid_amount and grand_total > 0
            else None
        )

        created = []
        for idx, item in enumerate(items):
            product = item.get('product')
            if not product:
                new_product_data = dict(item['new_product'])
                new_product_data.setdefault('purchase_price', item.get('unit_price'))
                new_product_data.setdefault('selling_price', item.get('selling_price'))
                new_product_data.setdefault('delivery_price', item.get('delivery_price'))
                if item.get('vat_percent'):
                    new_product_data.setdefault('vat_percent', item['vat_percent'])
                product = create_import_product(new_product_data)
            else:
                _sync_product_import_prices(product, item)
            line_paid = Decimal('0')
            if line_paid_splits is not None:
                line_paid = line_paid_splits[idx]
            elif payment_status == Zakaz.PAID and line_totals[idx] > 0:
                line_paid = line_totals[idx]
            zakaz = Zakaz.objects.create(
                product=product,
                zakaz_type=Zakaz.MANUAL,
                quantity=item['quantity'],
                unit_price=item.get('unit_price'),
                selling_price=item.get('selling_price'),
                delivery_price=item.get('delivery_price'),
                vat_percent=(item.get('vat_percent')
                             or product.vat_percent or 'none'),
                currency=item.get('currency') or currency,
                payment_status=payment_status,
                paid_amount=line_paid,
                supplier=item.get('supplier') or common_supplier,
                expected_date=item.get('expected_date') or common_expected,
                contract_number=contract_number,
                contract_date=contract_date,
                comment=item.get('comment'),
                status=Zakaz.NEW,
                import_batch=batch_id,
                created_by=user if user.is_authenticated else None,
            )
            ZakazHistory.objects.create(
                zakaz=zakaz, changed_by=zakaz.created_by,
                action=ZakazHistory.CREATED, new_status=Zakaz.NEW,
                contract_number=contract_number, contract_date=contract_date,
                asos='Bulk zakaz yaratildi.',
            )
            register_contract(
                zakaz.product, ProductContract.ZAKAZ_CREATED,
                contract_number=contract_number, contract_date=contract_date,
                asos='Bulk zakaz yaratildi.', zakaz=zakaz,
                user=zakaz.created_by,
            )
            if zakaz.total:
                from apps.orders.zakaz_payment import sync_zakaz_expense
                sync_zakaz_expense(zakaz, user=zakaz.created_by)
            if zakaz.payment_status == Zakaz.PAID:
                zakaz.receive(user=zakaz.created_by)
            created.append(zakaz)
        return created

    def to_representation(self, instance):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        serializer_class = zakaz_serializer_class(user)
        return {'zakazlar': serializer_class(instance, many=True, context=self.context).data}
