from decimal import Decimal

from rest_framework.serializers import (ModelSerializer, Serializer,
                                        SerializerMethodField,
                                        ValidationError, ReadOnlyField,
                                        DecimalField, CharField)

from apps.cash.models import Payment, PaymentTransaction


class PaymentTransactionSerializer(ModelSerializer):
    """Bitta to'lov (bo'lib to'lash) tranzaksiyasi."""
    received_by_name = SerializerMethodField()

    class Meta:
        model  = PaymentTransaction
        fields = ('id', 'amount', 'received_by', 'received_by_name',
                  'comment', 'created_at')

    def get_received_by_name(self, obj):
        return str(obj.received_by) if obj.received_by else None


class PaymentSerializer(ModelSerializer):
    sale_info    = SerializerMethodField()
    order_info   = SerializerMethodField()
    client_name  = SerializerMethodField()
    remaining    = SerializerMethodField()
    source       = SerializerMethodField()
    transactions = PaymentTransactionSerializer(many=True, read_only=True)

    class Meta:
        model  = Payment
        fields = (
            'id', 'source',
            'sale', 'sale_info',
            'order', 'order_info',
            'client', 'client_name',
            'total_amount', 'commission', 'paid_amount',
            'remaining', 'currency', 'due_date',
            'status', 'comment', 'created_at',
            'transactions',
        )
        read_only_fields = ('total_amount', 'commission', 'status', 'created_at')

    def get_source(self, obj):
        """To'lov manbai: sotuv yoki buyurtma."""
        if obj.order_id:
            return 'order'
        if obj.sale_id:
            return 'sale'
        return None

    def get_sale_info(self, obj):
        s = obj.sale
        if s is None:
            return None
        return {
            'id':          s.pk,
            'product':     str(s.product),
            'quantity':    s.quantity,
            'sold_price':  str(s.sold_price),
            'sold_date':   s.sold_date,
        }

    def get_order_info(self, obj):
        o = obj.order
        if o is None:
            return None
        return {
            'id':              o.pk,
            'product':         str(o.product),
            'quantity':        o.quantity,
            'unit_price':      str(o.unit_price) if o.unit_price is not None else None,
            'total':           str(o.total) if o.total is not None else None,
            'prepaid_amount':  str(o.prepaid_amount),
            'balance_due':     str(o.balance_due) if o.balance_due is not None else None,
            'contract_number': o.contract_number,
            'contract_date':   o.contract_date,
            'status':          o.status,
        }

    def get_client_name(self, obj):
        return str(obj.client) if obj.client else None

    def get_remaining(self, obj):
        return str(obj.total_amount - obj.paid_amount)

    def validate_paid_amount(self, value):
        if value < Decimal('0'):
            raise ValidationError('Toʻlov summasi manfiy boʻlishi mumkin emas.')
        return value

    def validate(self, attrs):
        # Yangi to'lov sotuvga YOKI buyurtmaga bog'lanishi shart
        if self.instance is None:
            if not attrs.get('sale') and not attrs.get('order'):
                raise ValidationError(
                    'To\'lov sotuv (sale) yoki buyurtma (order) ga bog\'lanishi kerak.')
            if attrs.get('sale') and attrs.get('order'):
                raise ValidationError(
                    'To\'lov bir vaqtda ham sotuv, ham buyurtmaga bog\'lana olmaydi.')
        return attrs


class PaymentUpdateSerializer(ModelSerializer):
    class Meta:
        model  = Payment
        fields = ('paid_amount', 'currency', 'due_date', 'comment')

    def update(self, instance, validated_data):
        """
        paid_amount to'g'ridan-to'g'ri o'zgartirilsa ham tranzaksiya
        yozilib boradi (ledger doim yig'indiga teng bo'lib qolsin).
        """
        new_paid = validated_data.get('paid_amount')
        if new_paid is not None and new_paid != instance.paid_amount:
            diff = new_paid - instance.paid_amount
            user = self.context.get('request').user if self.context.get('request') else None
            instance.transactions.create(
                amount=diff, received_by=user,
                comment='Kassa orqali to\'g\'ridan-to\'g\'ri o\'zgartirildi',
            )
            # Buyurtma to'lovi bo'lsa — buyurtmadagi oldindan to'lov sinxron
            if instance.order_id:
                instance.order.prepaid_amount = new_paid
                instance.order.save(update_fields=['prepaid_amount'])
        return super().update(instance, validated_data)


class PaymentPaySerializer(Serializer):
    """Qo'shimcha to'lov qabul qilish uchun body."""
    amount  = DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    comment = CharField(required=False, allow_blank=True, allow_null=True)
