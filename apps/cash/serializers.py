from decimal import Decimal

from rest_framework.serializers import (ModelSerializer, SerializerMethodField,
                                        ValidationError, ReadOnlyField)

from apps.cash.models import Payment


class PaymentSerializer(ModelSerializer):
    sale_info    = SerializerMethodField()
    client_name  = SerializerMethodField()
    remaining    = SerializerMethodField()

    class Meta:
        model  = Payment
        fields = (
            'id', 'sale', 'sale_info',
            'client', 'client_name',
            'total_amount', 'commission', 'paid_amount',
            'remaining', 'currency', 'due_date',
            'status', 'comment', 'created_at',
        )
        read_only_fields = ('total_amount', 'commission', 'status', 'created_at')

    def get_sale_info(self, obj):
        s = obj.sale
        return {
            'id':          s.pk,
            'product':     str(s.product),
            'quantity':    s.quantity,
            'sold_price':  str(s.sold_price),
            'sold_date':   s.sold_date,
        }

    def get_client_name(self, obj):
        return str(obj.client) if obj.client else None

    def get_remaining(self, obj):
        return str(obj.total_amount - obj.paid_amount)

    def validate_paid_amount(self, value):
        if value < Decimal('0'):
            raise ValidationError('Toʻlov summasi manfiy boʻlishi mumkin emas.')
        return value


class PaymentUpdateSerializer(ModelSerializer):
    class Meta:
        model  = Payment
        fields = ('paid_amount', 'currency', 'due_date', 'comment')
