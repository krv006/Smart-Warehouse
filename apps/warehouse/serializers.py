from rest_framework.serializers import (ModelSerializer, ValidationError,
                                        IntegerField, CharField, SerializerMethodField)

from apps.warehouse.models import Category, Product, Stock


class CategorySerializer(ModelSerializer):
    children = SerializerMethodField()

    class Meta:
        model  = Category
        fields = ('id', 'name', 'parent', 'children')

    def get_children(self, obj):
        return CategorySerializer(obj.children.all(), many=True).data


def _validate_stock_fields(attrs):
    if attrs.get('quantity') and not attrs.get('warehouse_location'):
        raise ValidationError({
            'warehouse_location': 'Miqdor kiritilganda lokatsiya (warehouse_location) ham kiritilishi shart.'
        })
    return attrs


class ProductSerializer(ModelSerializer):
    quantity_in_stock  = IntegerField(read_only=True)
    reserved_quantity  = IntegerField(read_only=True)
    available_quantity = IntegerField(read_only=True)
    stock_status       = SerializerMethodField()
    category_name      = SerializerMethodField()
    quantity            = IntegerField(write_only=True, required=False, min_value=1)
    warehouse_location  = CharField(write_only=True, required=False,
                                    allow_blank=True, max_length=255)

    class Meta:
        model  = Product
        fields = ('id', 'category', 'category_name', 'name', 'model',
                  'serial_number', 'purchase_price', 'selling_price', 'source',
                  'min_quantity', 'quantity_in_stock', 'reserved_quantity',
                  'available_quantity', 'stock_status',
                  'quantity', 'warehouse_location', 'created_at')
        read_only_fields = ('created_at',)

    def get_stock_status(self, obj):
        return obj.stock_status

    def get_category_name(self, obj):
        return str(obj.category) if obj.category else None

    def validate(self, attrs):
        return _validate_stock_fields(attrs)

    def create(self, validated_data):
        quantity = validated_data.get('quantity')
        location = validated_data.get('warehouse_location')
        validated_data.pop('quantity', None)
        validated_data.pop('warehouse_location', None)
        product = super().create(validated_data)
        if quantity:
            Stock.objects.create(product=product, quantity=quantity, warehouse_location=location)
        return product

    def update(self, instance, validated_data):
        validated_data.pop('quantity', None)
        validated_data.pop('warehouse_location', None)
        product = super().update(instance, validated_data)
        from apps.notifications.models import Notification
        if product.purchase_price is not None:
            Notification.resolve_price_notifications(product)
        # low_stock check after min_quantity may have changed
        if product.quantity_in_stock <= product.min_quantity and product.quantity_in_stock > 0:
            Notification.notify_low_stock(product)
        elif product.quantity_in_stock > product.min_quantity:
            Notification.resolve_low_stock_notifications(product)
        return product


class ProductOperatorSerializer(ModelSerializer):
    """Operator uchun — purchase_price/selling_price yashirin va kiritib bo'lmaydi."""
    quantity_in_stock  = IntegerField(read_only=True)
    reserved_quantity  = IntegerField(read_only=True)
    available_quantity = IntegerField(read_only=True)
    stock_status       = SerializerMethodField()
    category_name      = SerializerMethodField()
    quantity            = IntegerField(write_only=True, required=False, min_value=1)
    warehouse_location  = CharField(write_only=True, required=False,
                                    allow_blank=True, max_length=255)

    class Meta:
        model  = Product
        fields = ('id', 'category', 'category_name', 'name', 'model',
                  'serial_number', 'source', 'min_quantity', 'quantity_in_stock',
                  'reserved_quantity', 'available_quantity', 'stock_status',
                  'quantity', 'warehouse_location', 'created_at')
        read_only_fields = ('created_at',)

    def get_stock_status(self, obj):
        return obj.stock_status

    def get_category_name(self, obj):
        return str(obj.category) if obj.category else None

    def validate(self, attrs):
        return _validate_stock_fields(attrs)

    def update(self, instance, validated_data):
        validated_data.pop('quantity', None)
        validated_data.pop('warehouse_location', None)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        quantity = validated_data.get('quantity')
        location = validated_data.get('warehouse_location')
        validated_data.pop('quantity', None)
        validated_data.pop('warehouse_location', None)
        product = super().create(validated_data)
        if quantity:
            Stock.objects.create(product=product, quantity=quantity, warehouse_location=location)
        from apps.notifications.models import Notification
        Notification.notify_missing_price(product)
        return product


class StockSerializer(ModelSerializer):
    product_name      = SerializerMethodField()
    product_model     = SerializerMethodField()
    min_quantity      = SerializerMethodField()
    stock_status      = SerializerMethodField()

    class Meta:
        model  = Stock
        fields = ('id', 'product', 'product_name', 'product_model',
                  'quantity', 'reserved_quantity', 'warehouse_location',
                  'min_quantity', 'stock_status')

    def get_product_name(self, obj):
        return str(obj.product)

    def get_product_model(self, obj):
        return obj.product.model

    def get_min_quantity(self, obj):
        return obj.product.min_quantity

    def get_stock_status(self, obj):
        return obj.product.stock_status

    def update(self, instance, validated_data):
        stock = super().update(instance, validated_data)
        from apps.notifications.models import Notification
        from apps.orders.models import allocate_pending_orders
        product = stock.product
        # Yangi kirim bo'lsa pending orderlarga bron ajrat
        allocate_pending_orders(product)
        # Low stock notification
        avail = product.available_quantity
        if avail <= 0 or avail <= product.min_quantity:
            Notification.notify_low_stock(product)
        else:
            Notification.resolve_low_stock_notifications(product)
        return stock

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
