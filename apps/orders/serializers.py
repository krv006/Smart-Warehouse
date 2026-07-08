import json

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import (ModelSerializer, Serializer,
                                        SerializerMethodField, ReadOnlyField,
                                        ValidationError, BooleanField,
                                        CharField, DateField,
                                        DecimalField, IntegerField,
                                        PrimaryKeyRelatedField)

from apps.clients.models import Client
from apps.orders.models import (Order, OrderItem, OrderHistory,
                                Zakaz, ZakazHistory,
                                ProductContract, register_contract,
                                allocate_pending_orders)
from apps.warehouse.models import Product

# Buyurtma sarlavha tahririda kuzatiladigan maydonlar (tarixga yoziladi)
_ORDER_TRACKED_FIELDS = ('client', 'prepaid_amount', 'contract_number',
                         'contract_date', 'due_date', 'comment')

_ZAKAZ_TRACKED_FIELDS = ('quantity', 'received_qty', 'supplier',
                         'contract_number', 'contract_date', 'asos', 'faktura',
                         'expected_date', 'warehouse_location', 'comment')


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
        fields = ('id', 'action', 'action_display', 'contract_number', 'asos',
                  'changes', 'changed_by', 'changed_by_name', 'created_at')

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

    # Shartnoma raqami — buyurtma olishda MAJBURIY
    contract_number = CharField(max_length=100, allow_blank=False,
                                error_messages={
                                    'blank':    'Shartnoma raqami kiritilishi shart.',
                                    'required': 'Shartnoma raqami kiritilishi shart.',
                                })
    contract_date   = DateField(required=False)

    # Tahrir asosi — modelda saqlanmaydi, tarixga yoziladi
    asos = CharField(write_only=True, required=False, allow_blank=True,
                     help_text='Tahrir/amal asosi (tahrirlashda majburiy)')

    # Eski (bitta mahsulotli) format ham qabul qilinadi — items ga aylanadi
    product    = PrimaryKeyRelatedField(queryset=Product.objects.all(),
                                        required=False, write_only=True)
    quantity   = IntegerField(required=False, min_value=1, write_only=True)
    unit_price = DecimalField(max_digits=14, decimal_places=2,
                              required=False, allow_null=True, write_only=True)

    class Meta:
        model  = Order
        fields = (
            'id', 'client', 'client_name',
            'items',
            'product', 'quantity', 'unit_price',   # legacy (write-only)
            'total_quantity', 'total',
            'prepaid_amount', 'balance_due',
            'contract_number', 'contract_date',
            'reserved_qty', 'backorder_qty',
            'has_active_zakaz',
            'due_date', 'status', 'comment', 'created_at',
            'asos', 'history',
        )
        read_only_fields = ('status', 'created_at')

    def get_client_name(self, obj):
        return str(obj.client) if obj.client else None

    def validate(self, attrs):
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
        user = self.context['request'].user

        # items yoki legacy (product/quantity/unit_price)
        items_data = validated_data.pop('items', None)
        product    = validated_data.pop('product', None)
        quantity   = validated_data.pop('quantity', None)
        unit_price = validated_data.pop('unit_price', None)
        if not items_data:
            items_data = [{'product': product, 'quantity': quantity or 1,
                           'unit_price': unit_price}]

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
    contract_number = CharField(max_length=100, allow_blank=False,
                                error_messages={
                                    'blank':    'Shartnoma raqami kiritilishi shart.',
                                    'required': 'Shartnoma raqami kiritilishi shart.',
                                })
    contract_date   = DateField(required=False)
    prepaid_amount  = DecimalField(max_digits=14, decimal_places=2,
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
        # instance — yaratilgan BITTA Order
        return {'order': OrderSerializer(instance).data}


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
                  'order', 'zakaz',
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

class ZakazSerializer(ModelSerializer):
    product_name       = SerializerMethodField()
    created_by_name    = SerializerMethodField()
    status_display     = SerializerMethodField()
    order_contract     = SerializerMethodField()
    warehouse_location = CharField(required=False, allow_null=True,
                                   allow_blank=True, max_length=255)
    history            = ZakazHistorySerializer(many=True, read_only=True)

    class Meta:
        model  = Zakaz
        fields = (
            'id', 'order', 'order_contract',
            'product', 'product_name',
            'quantity', 'received_qty',
            'supplier', 'status', 'status_display',
            'contract_number', 'contract_date', 'confirmed_at',
            'asos', 'faktura',
            'expected_date', 'warehouse_location',
            'created_by', 'created_by_name',
            'comment', 'created_at',
            'history',
        )
        read_only_fields = ('created_by', 'confirmed_at', 'created_at')

    def get_product_name(self, obj):
        return str(obj.product)

    def get_created_by_name(self, obj):
        return str(obj.created_by) if obj.created_by else None

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_order_contract(self, obj):
        """Manba buyurtmaning shartnoma raqami (asos zanjiri)."""
        if obj.order_id:
            return {'order': obj.order_id,
                    'contract_number': obj.order.contract_number,
                    'contract_date': str(obj.order.contract_date)}
        return None

    def create(self, validated_data):
        # Status har doim 'new' dan boshlanadi
        validated_data['status']     = Zakaz.NEW
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
        return zakaz

    # Har bir status o'zgarishi → reestrga qaysi turda yozilishi
    _CONTRACT_SOURCE = {
        Zakaz.CONFIRMED: ProductContract.ZAKAZ_CONFIRMED,
        Zakaz.ORDERED:   ProductContract.ZAKAZ_ORDERED,
        Zakaz.RECEIVED:  ProductContract.ZAKAZ_RECEIVED,
        Zakaz.CANCELLED: ProductContract.ZAKAZ_CANCELLED,
    }

    def update(self, instance, validated_data):
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
            if new_status in (Zakaz.CONFIRMED, Zakaz.ORDERED, Zakaz.RECEIVED):
                if not (validated_data.get('contract_date') or instance.contract_date):
                    validated_data['contract_date'] = timezone.localdate()
            if new_status == Zakaz.CONFIRMED:
                validated_data['confirmed_at'] = timezone.now()

        old_status   = instance.status
        was_received = instance.status == Zakaz.RECEIVED
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

        return zakaz


class ZakazItemSerializer(Serializer):
    """Bulk zakaz ichidagi bitta mahsulot qatori."""
    product       = PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity      = IntegerField(min_value=1)
    supplier      = CharField(required=False, allow_blank=True, allow_null=True)
    expected_date = DateField(required=False, allow_null=True)
    comment       = CharField(required=False, allow_blank=True, allow_null=True)


class ZakazBulkCreateSerializer(Serializer):
    """
    Bir vaqtda bir nechta mahsulot uchun zakaz.
    Har biri alohida Zakaz yozuvi bo'ladi (status="new").

    Namuna:
    {
      "supplier": "Xitoy, Guangzhou",
      "expected_date": "2026-08-15",
      "contract_number": "SH-2026/045",
      "items": [
        { "product": 12, "quantity": 7 },
        { "product": 7,  "quantity": 5, "supplier": "UAE, Dubai" }
      ]
    }
    """
    supplier        = CharField(required=False, allow_blank=True, allow_null=True)
    expected_date   = DateField(required=False, allow_null=True)
    contract_number = CharField(required=False, allow_blank=True, allow_null=True)
    contract_date   = DateField(required=False, allow_null=True)
    items           = ZakazItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise ValidationError('Kamida bitta mahsulot kiritilishi kerak.')
        # Faol zakaz bor mahsulotга takror zakaz bermaslik
        errors = []
        for item in value:
            product = item['product']
            has_active = product.zakazlar.filter(
                status__in=(Zakaz.NEW, Zakaz.CONFIRMED, Zakaz.ORDERED)
            ).exists()
            if has_active:
                errors.append(
                    f'"{product.name}" — bu mahsulot uchun faol zakaz allaqachon mavjud.'
                )
        if errors:
            raise ValidationError(errors)
        return value

    def create(self, validated_data):
        common_supplier = validated_data.get('supplier')
        common_expected = validated_data.get('expected_date')
        contract_number = validated_data.get('contract_number')
        contract_date   = validated_data.get('contract_date')
        items           = validated_data['items']
        user            = self.context['request'].user

        created = []
        for item in items:
            zakaz = Zakaz.objects.create(
                product=item['product'],
                quantity=item['quantity'],
                supplier=item.get('supplier') or common_supplier,
                expected_date=item.get('expected_date') or common_expected,
                contract_number=contract_number,
                contract_date=contract_date,
                comment=item.get('comment'),
                status=Zakaz.NEW,
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
            created.append(zakaz)
        return created

    def to_representation(self, instance):
        return {'zakazlar': ZakazSerializer(instance, many=True).data}
