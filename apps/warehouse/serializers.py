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


class ProductOperatorSerializer(ModelSerializer):
    """Operator uchun — purchase_price yashirin."""
    quantity_in_stock = IntegerField(read_only=True)
    category_name     = SerializerMethodField()

    class Meta:
        model  = Product
        fields = ('id', 'category', 'category_name', 'name', 'model',
                  'serial_number', 'source', 'quantity_in_stock', 'created_at')
        read_only_fields = ('created_at',)

    def get_category_name(self, obj):
        return str(obj.category) if obj.category else None


class StockSerializer(ModelSerializer):
    product_name = SerializerMethodField()

    class Meta:
        model  = Stock
        fields = ('id', 'product', 'product_name', 'quantity', 'warehouse_location')

    def get_product_name(self, obj):
        return str(obj.product)

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
