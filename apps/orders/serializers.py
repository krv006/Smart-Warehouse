import json

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import (ModelSerializer, Serializer,
                                        SerializerMethodField, ReadOnlyField,
                                        ValidationError, CharField, DateField,
                                        DecimalField, IntegerField,
                                        PrimaryKeyRelatedField)

from apps.clients.models import Client
from apps.orders.models import Order, OrderHistory, Zakaz, ZakazHistory
from apps.warehouse.models import Product

# Buyurtma tahririda kuzatiladigan maydonlar (tarixga yoziladi)
_ORDER_TRACKED_FIELDS = ('client', 'product', 'quantity', 'unit_price',
                         'prepaid_amount', 'contract_number', 'contract_date',
                         'due_date', 'comment')

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


# ── Order (Bron) ──────────────────────────────────────────────────────────────

class OrderSerializer(ModelSerializer):
    product_name     = SerializerMethodField()
    client_name      = SerializerMethodField()
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

    class Meta:
        model  = Order
        fields = (
            'id', 'client', 'client_name',
            'product', 'product_name',
            'quantity', 'unit_price', 'total',
            'prepaid_amount', 'balance_due',
            'contract_number', 'contract_date',
            'reserved_qty', 'backorder_qty',
            'has_active_zakaz',
            'due_date', 'status', 'comment', 'created_at',
            'asos', 'history',
        )
        read_only_fields = ('reserved_qty', 'status', 'created_at')

    def get_product_name(self, obj):
        return str(obj.product)

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
        return attrs

    # Eslatma: buyurtma (Order) HAR DOIM yaratiladi.
    # Qoldiq yetmasa — backorder bo'lib qoladi va yetishmagan miqdor uchun
    # AVTOMATIK Zakaz ochiladi (o'sha shartnoma raqami asosida).

    def create(self, validated_data):
        validated_data.pop('asos', None)
        validated_data.setdefault('contract_date', timezone.localdate())
        user = self.context['request'].user

        order = super().create(validated_data)
        order.reserve()

        # Tarix: yaratildi (shartnoma raqami + aniq sana/vaqt)
        OrderHistory.objects.create(
            order=order, changed_by=user, action=OrderHistory.CREATED,
            contract_number=order.contract_number,
            asos=f'Buyurtma yaratildi — shartnoma №{order.contract_number}.',
        )

        # 2-etap: yetishmagan miqdor avtomatik Zakazga o'tadi
        order.create_backorder_zakaz(user=user)
        return order

    def update(self, instance, validated_data):
        asos = validated_data.pop('asos', '')
        user = self.context['request'].user

        changes = _diff(instance, validated_data, _ORDER_TRACKED_FIELDS)
        old_quantity = instance.quantity

        order = super().update(instance, validated_data)

        # Miqdor o'zgargan bo'lsa — bronni qayta moslash
        if order.quantity != old_quantity:
            order.resync_reservation()

        # Tarix: har bir tahrir shartnoma raqami + asos + sana/vaqt bilan
        OrderHistory.objects.create(
            order=order, changed_by=user, action=OrderHistory.EDITED,
            contract_number=order.contract_number,
            asos=asos,
            changes=json.dumps(changes, ensure_ascii=False) if changes else None,
        )
        return order


class OrderItemSerializer(ModelSerializer):
    """Bulk buyurtma ichidagi bitta mahsulot qatori."""
    prepaid_amount = DecimalField(max_digits=14, decimal_places=2,
                                  required=False, default=0)

    class Meta:
        model  = Order
        fields = ('product', 'quantity', 'unit_price', 'prepaid_amount', 'comment')


class OrderBulkCreateSerializer(Serializer):
    """
    Bir vaqtda bir nechta mahsulot buyurtmasi.
    Har bir mahsulot alohida Order yozuvi bo'ladi (bitta client/due_date/
    shartnoma ostida). Yetishmagan miqdorlar uchun avtomatik Zakaz ochiladi.

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
                                   required=False, allow_null=True,
                                   help_text='Umumiy oldindan to\'lov — birinchi qatorga yoziladi')
    items           = OrderItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise ValidationError('Kamida bitta mahsulot kiritilishi kerak.')
        return value

    def create(self, validated_data):
        client          = validated_data.get('client')
        due_date        = validated_data.get('due_date')
        contract_number = validated_data['contract_number']
        contract_date   = validated_data.get('contract_date') or timezone.localdate()
        common_prepaid  = validated_data.get('prepaid_amount')
        items           = validated_data['items']
        user            = self.context['request'].user

        created = []
        for i, item in enumerate(items):
            prepaid = item.get('prepaid_amount') or 0
            # Umumiy oldindan to'lov ko'rsatilgan bo'lsa — birinchi qatorga
            if i == 0 and common_prepaid and not prepaid:
                prepaid = common_prepaid
            order = Order.objects.create(
                client=client,
                due_date=due_date,
                contract_number=contract_number,
                contract_date=contract_date,
                product=item['product'],
                quantity=item['quantity'],
                unit_price=item.get('unit_price'),
                prepaid_amount=prepaid,
                comment=item.get('comment'),
            )
            order.reserve()
            OrderHistory.objects.create(
                order=order, changed_by=user, action=OrderHistory.CREATED,
                contract_number=contract_number,
                asos=f'Bulk buyurtma — shartnoma №{contract_number}.',
            )
            # 2-etap: yetishmagan miqdor avtomatik Zakazga
            order.create_backorder_zakaz(user=user)
            created.append(order)
        return created

    def to_representation(self, instance):
        # instance — yaratilgan Order ro'yxati
        return {'orders': OrderSerializer(instance, many=True).data}


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
        return zakaz

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

            # TASDIQLASH: shartnoma kiritilmaguncha tasdiqlab bo'lmaydi
            if new_status == Zakaz.CONFIRMED:
                contract = validated_data.get('contract_number') or instance.contract_number
                if not contract:
                    raise ValidationError({
                        'contract_number': 'Shartnoma (dogavor) kiritilmaguncha '
                                           'zakazni tasdiqlab bo\'lmaydi.'
                    })
                # Sana: yangi shartnoma bo'lsa — bugungi kun (Tashkent);
                # buyurtmadan kelgan (eski) shartnoma bo'lsa — o'sha kun saqlanadi
                if not (validated_data.get('contract_date') or instance.contract_date):
                    validated_data['contract_date'] = timezone.localdate()
                validated_data['confirmed_at'] = timezone.now()

            # QABUL QILISH: asos + faktura majburiy
            if new_status == Zakaz.RECEIVED:
                asos    = validated_data.get('asos') or instance.asos
                faktura = validated_data.get('faktura') or instance.faktura
                errors  = {}
                if not asos:
                    errors['asos'] = 'Qabul qilish uchun asos kiritilishi shart.'
                if not faktura:
                    errors['faktura'] = 'Qabul qilish uchun faktura kiritilishi shart.'
                if errors:
                    raise ValidationError(errors)

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
        elif changes:
            ZakazHistory.objects.create(
                zakaz=zakaz, changed_by=user, action=ZakazHistory.EDITED,
                contract_number=zakaz.contract_number,
                contract_date=zakaz.contract_date,
                asos=zakaz.asos, faktura=zakaz.faktura,
                changes=json.dumps(changes, ensure_ascii=False),
            )

        # Birinchi marta 'received' ga o'tganda ombor to'ldir
        if zakaz.status == Zakaz.RECEIVED and not was_received:
            zakaz.receive()

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
            created.append(zakaz)
        return created

    def to_representation(self, instance):
        return {'zakazlar': ZakazSerializer(instance, many=True).data}
