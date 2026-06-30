from rest_framework.serializers import (ModelSerializer, SerializerMethodField,
                                        ValidationError, ReadOnlyField)

from apps.orders.models import Order


class OrderSerializer(ModelSerializer):
    product_name  = SerializerMethodField()
    client_name   = SerializerMethodField()
    backorder_qty = ReadOnlyField()

    class Meta:
        model  = Order
        fields = ('id', 'client', 'client_name', 'product', 'product_name',
                  'quantity', 'reserved_qty', 'backorder_qty',
                  'due_date', 'status', 'comment', 'created_at')
        read_only_fields = ('reserved_qty', 'status', 'created_at')

    def get_product_name(self, obj):
        return str(obj.product)

    def get_client_name(self, obj):
        return str(obj.client) if obj.client else None

    def create(self, validated_data):
        order = super().create(validated_data)
        order.reserve()
        return order
