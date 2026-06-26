from django.db import transaction
from django.db.models import F
from rest_framework.serializers import (ModelSerializer, ValidationError,
                                        DecimalField, SerializerMethodField)

from apps.sales.models import Sale
from apps.warehouse.models import Stock


class SaleSerializer(ModelSerializer):
    total_amount = DecimalField(max_digits=14, decimal_places=2, read_only=True)
    profit       = DecimalField(max_digits=14, decimal_places=2, read_only=True)
    product_name = SerializerMethodField()

    class Meta:
        model  = Sale
        fields = ('id', 'product', 'product_name', 'quantity', 'sold_price',
                  'total_amount', 'profit', 'sold_to', 'destination',
                  'sold_date', 'comment', 'created_at')
        read_only_fields = ('created_at',)

    def get_product_name(self, obj):
        return str(obj.product)

    def validate_quantity(self, value):
        if value <= 0:
            raise ValidationError("Miqdor noldan katta bo'lishi kerak.")
        return value

    def validate(self, attrs):
        product   = attrs.get('product', getattr(self.instance, 'product', None))
        quantity  = attrs.get('quantity', getattr(self.instance, 'quantity', 0))
        available = product.quantity_in_stock if product else 0
        if quantity > available:
            raise ValidationError({
                'quantity': (
                    f'"{product.name}" uchun omborda yetarli qoldiq yo\'q. '
                    f'Mavjud: {available}, so\'ralgan: {quantity}.'
                )
            })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        sale      = super().create(validated_data)
        remaining = sale.quantity
        stocks    = (sale.product.stocks
                     .select_for_update()
                     .filter(quantity__gt=0)
                     .order_by('id'))
        for stock in stocks:
            if remaining <= 0:
                break
            take = min(stock.quantity, remaining)
            stock.quantity = F('quantity') - take
            stock.save(update_fields=['quantity'])
            remaining -= take
        return sale
