from django.db import transaction
from django.db.models import F
from rest_framework.serializers import (ModelSerializer, ValidationError,
                                         IntegerField, DecimalField)

from apps.models import Product, Stock, Sale


class ProductSerializer(ModelSerializer):
    quantity_in_stock = IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'model', 'serial_number', 'purchase_price',
            'quantity_in_stock', 'created_at',
        )
        read_only_fields = ('created_at',)


class StockSerializer(ModelSerializer):
    class Meta:
        model = Stock
        fields = ('id', 'product', 'quantity', 'warehouse_location')

    def validate(self, attrs):
        # unique_together (product, warehouse_location) — tushunarli xabar beramiz
        product = attrs.get('product', getattr(self.instance, 'product', None))
        location = attrs.get('warehouse_location',
                             getattr(self.instance, 'warehouse_location', None))
        qs = Stock.objects.filter(product=product, warehouse_location=location)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                'Bu mahsulot uchun ushbu lokatsiyada qoldiq allaqachon mavjud. '
                'Mavjud yozuvni tahrirlang.'
            )
        return attrs


class SaleSerializer(ModelSerializer):
    total_amount = DecimalField(max_digits=14, decimal_places=2, read_only=True)
    profit = DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Sale
        fields = (
            'id', 'product', 'sold_price', 'quantity', 'sold_to',
            'sold_date', 'comment', 'total_amount', 'profit', 'created_at',
        )
        read_only_fields = ('created_at',)

    def validate_quantity(self, value):
        if value <= 0:
            raise ValidationError('Miqdor noldan katta bo\'lishi kerak.')
        return value

    def validate(self, attrs):
        product = attrs['product']
        quantity = attrs['quantity']
        available = product.quantity_in_stock
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
        """Sotuvni yozamiz va ombor qoldig'idan miqdorni ayiramiz (FIFO)."""
        sale = super().create(validated_data)
        remaining = sale.quantity
        stocks = (sale.product.stocks
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
