from rest_framework.serializers import (ModelSerializer, ValidationError,
                                        IntegerField, SerializerMethodField)

from apps.warehouse.models import Category, Product, Stock


class CategorySerializer(ModelSerializer):
    children = SerializerMethodField()

    class Meta:
        model  = Category
        fields = ('id', 'name', 'parent', 'children')

    def get_children(self, obj):
        return CategorySerializer(obj.children.all(), many=True).data


class ProductSerializer(ModelSerializer):
    quantity_in_stock = IntegerField(read_only=True)
    category_name     = SerializerMethodField()

    class Meta:
        model  = Product
        fields = ('id', 'category', 'category_name', 'name', 'model',
                  'serial_number', 'purchase_price', 'source',
                  'quantity_in_stock', 'created_at')
        read_only_fields = ('created_at',)

    def get_category_name(self, obj):
        return str(obj.category) if obj.category else None

    def update(self, instance, validated_data):
        product = super().update(instance, validated_data)
        if product.purchase_price is not None:
            from apps.notifications.models import Notification
            Notification.resolve_price_notifications(product)
        return product


class ProductOperatorSerializer(ModelSerializer):
    """Operator uchun — purchase_price yashirin va kiritib bo'lmaydi."""
    quantity_in_stock = IntegerField(read_only=True)
    category_name     = SerializerMethodField()

    class Meta:
        model  = Product
        fields = ('id', 'category', 'category_name', 'name', 'model',
                  'serial_number', 'source', 'quantity_in_stock', 'created_at')
        read_only_fields = ('created_at',)

    def get_category_name(self, obj):
        return str(obj.category) if obj.category else None

    def create(self, validated_data):
        product = super().create(validated_data)
        from apps.notifications.models import Notification
        Notification.notify_missing_price(product)
        return product


class StockSerializer(ModelSerializer):
    product_name  = SerializerMethodField()
    product_model = SerializerMethodField()

    class Meta:
        model  = Stock
        fields = ('id', 'product', 'product_name', 'product_model',
                  'quantity', 'warehouse_location')

    def get_product_name(self, obj):
        return str(obj.product)

    def get_product_model(self, obj):
        return obj.product.model

    def validate(self, attrs):
        product  = attrs.get('product',  getattr(self.instance, 'product',  None))
        location = attrs.get('warehouse_location',
                             getattr(self.instance, 'warehouse_location', None))
        qs = Stock.objects.filter(product=product, warehouse_location=location)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                'Bu mahsulot uchun ushbu lokatsiyada qoldiq allaqachon mavjud.'
            )
        return attrs
