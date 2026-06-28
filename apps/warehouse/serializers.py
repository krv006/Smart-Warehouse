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
        if product.purchase_price is None:
            self._notify_management_missing_price(product)
        return product

    @staticmethod
    def _notify_management_missing_price(product):
        from django.contrib.auth import get_user_model
        from apps.notifications.models import Notification

        User = get_user_model()
        category = str(product.category) if product.category else '—'
        message = (
            f'"{product.name}" ({product.serial_number}) mahsuloti narxsiz qo\'shildi.\n'
            f'Kategoriya: {category}\n'
            f'Model: {product.model or "—"}\n'
            f'Manba: {product.source or "—"}\n'
            'Iltimos, kelish narxini kiriting.'
        )
        managers = User.objects.filter(role=User.MANAGEMENT, is_active=True)
        Notification.objects.bulk_create([
            Notification(recipient=manager, title='Narxsiz mahsulot qo\'shildi', message=message)
            for manager in managers
        ])


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
