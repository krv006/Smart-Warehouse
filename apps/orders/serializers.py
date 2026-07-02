from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import (ModelSerializer, SerializerMethodField,
                                        ReadOnlyField, ValidationError, CharField)

from apps.orders.models import Order, Zakaz


# ── Order (Bron) ──────────────────────────────────────────────────────────────

class OrderSerializer(ModelSerializer):
    product_name  = SerializerMethodField()
    client_name   = SerializerMethodField()
    backorder_qty = ReadOnlyField()

    class Meta:
        model  = Order
        fields = (
            'id', 'client', 'client_name',
            'product', 'product_name',
            'quantity', 'reserved_qty', 'backorder_qty',
            'due_date', 'status', 'comment', 'created_at',
        )
        read_only_fields = ('reserved_qty', 'status', 'created_at')

    def get_product_name(self, obj):
        return str(obj.product)

    def get_client_name(self, obj):
        return str(obj.client) if obj.client else None

    def validate(self, attrs):
        # Yangi order yaratishda (not update) available_quantity tekshirish
        if self.instance is None:
            product = attrs.get('product')
            if product and product.available_quantity <= 0:
                raise ValidationError({
                    'product': (
                        f'"{product.name}" mahsuloti to\'liq bron qilingan yoki '
                        f'omborda qolmagan (mavjud: 0 dona). '
                        f'Mahsulot kelishi uchun Zakaz bering.'
                    )
                })
        return attrs

    def create(self, validated_data):
        order = super().create(validated_data)
        order.reserve()
        return order


# ── Zakaz (Etkazuvchidan buyurtma) ────────────────────────────────────────────

class ZakazSerializer(ModelSerializer):
    product_name       = SerializerMethodField()
    created_by_name    = SerializerMethodField()
    status_display     = SerializerMethodField()
    warehouse_location = CharField(required=False, allow_null=True,
                                   allow_blank=True, max_length=255)

    class Meta:
        model  = Zakaz
        fields = (
            'id', 'product', 'product_name',
            'quantity', 'received_qty',
            'supplier', 'status', 'status_display',
            'expected_date', 'warehouse_location',
            'created_by', 'created_by_name',
            'comment', 'created_at',
        )
        read_only_fields = ('created_by', 'created_at')

    def get_product_name(self, obj):
        return str(obj.product)

    def get_created_by_name(self, obj):
        return str(obj.created_by) if obj.created_by else None

    def get_status_display(self, obj):
        return obj.get_status_display()

    def create(self, validated_data):
        # Status har doim 'new' dan boshlanadi
        validated_data['status']     = Zakaz.NEW
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user       = self.context['request'].user
        new_status = validated_data.get('status')

        # Status o'zgartirish — faqat Management
        if new_status and new_status != instance.status:
            if not getattr(user, 'is_management', False):
                raise PermissionDenied(
                    'Status faqat boshqaruv (Management) tomonidan o\'zgartirilishi mumkin.'
                )
            # Bekor qilingan yoki qabul qilingan zakazni o'zgartirib bo'lmaydi
            if instance.status in (Zakaz.RECEIVED, Zakaz.CANCELLED):
                raise ValidationError(
                    f'"{instance.get_status_display()}" statusidagi zakazni o\'zgartirib bo\'lmaydi.'
                )

        was_received = instance.status == Zakaz.RECEIVED
        zakaz = super().update(instance, validated_data)

        # Birinchi marta 'received' ga o'tganda ombor to'ldir
        if zakaz.status == Zakaz.RECEIVED and not was_received:
            zakaz.receive()

        return zakaz
