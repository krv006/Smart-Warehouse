from django.db import transaction
from rest_framework.serializers import (ModelSerializer, ValidationError,
                                        IntegerField, CharField,
                                        PrimaryKeyRelatedField,
                                        SerializerMethodField)

from apps.warehouse.models import Product, Stock  # Category vaqtincha ishlatilmaydi
from apps.warehouse.product_utils import (normalize_product_serial,
                                          serial_number_is_taken)


# Kategoriya funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
# class CategorySerializer(ModelSerializer):
#     children = SerializerMethodField()
#
#     class Meta:
#         model  = Category
#         fields = ('id', 'name', 'parent', 'children')
#
#     def get_children(self, obj):
#         return CategorySerializer(obj.children.all(), many=True).data


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
    pending_import_quantity = IntegerField(read_only=True)
    stock_status       = SerializerMethodField()
    # Kategoriya funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
    # category_name      = SerializerMethodField()
    unit_display       = SerializerMethodField()
    origin_display     = SerializerMethodField()
    serial_number      = CharField(required=False, allow_blank=True,
                                   allow_null=True, max_length=255)
    # category           = PrimaryKeyRelatedField(queryset=Category.objects.all())
    quantity            = IntegerField(write_only=True, required=False, min_value=1)
    warehouse_location  = CharField(write_only=True, required=False,
                                    allow_blank=True, max_length=255)

    class Meta:
        model  = Product
        fields = ('id', 'name',
                  # Model funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
                  # 'model',
                  'serial_number', 'barcode', 'purchase_price', 'selling_price',
                  'delivery_price', 'vat_percent', 'source',
                  'origin', 'origin_display',
                  'unit', 'unit_display', 'min_quantity',
                  'quantity_in_stock', 'reserved_quantity',
                  'available_quantity', 'pending_import_quantity', 'stock_status',
                  'quantity', 'warehouse_location', 'created_at')
        read_only_fields = ('created_at',)

    def get_stock_status(self, obj):
        return obj.stock_status

    # def get_category_name(self, obj):
    #     return str(obj.category) if obj.category else None

    def get_unit_display(self, obj):
        return obj.get_unit_display()

    def get_origin_display(self, obj):
        return obj.get_origin_display()

    def validate(self, attrs):
        if 'serial_number' in attrs:
            attrs['serial_number'] = normalize_product_serial(attrs['serial_number'])
            # Seriya raqami noyob — takrorlansa 500 emas, tushunarli 400 qaytsin
            if serial_number_is_taken(attrs['serial_number'],
                                      exclude_pk=getattr(self.instance, 'pk', None)):
                raise ValidationError({
                    'serial_number': (f'"{attrs["serial_number"]}" seriya raqami boshqa '
                                      f'mahsulotda band — boshqa raqam kiriting.')})
        return _validate_stock_fields(attrs)

    def create(self, validated_data):
        quantity = validated_data.get('quantity')
        location = validated_data.get('warehouse_location')
        validated_data.pop('quantity', None)
        validated_data.pop('warehouse_location', None)
        validated_data['serial_number'] = normalize_product_serial(
            validated_data.get('serial_number')
        )
        product = super().create(validated_data)
        if quantity:
            Stock.objects.create(product=product, quantity=quantity, warehouse_location=location)
            from apps.warehouse.stock_expense import record_stock_in_expense
            request = self.context.get('request')
            record_stock_in_expense(
                product, quantity,
                user=getattr(request, 'user', None),
                asos='Mahsulot yaratishda boshlang\'ich qoldiq',
            )
        return product

    def update(self, instance, validated_data):
        validated_data.pop('quantity', None)
        validated_data.pop('warehouse_location', None)
        product = super().update(instance, validated_data)
        from apps.notifications.models import Notification
        if product.purchase_price is not None:
            Notification.resolve_price_notifications(product)
        # low_stock check after min_quantity may have changed
        avail = product.available_quantity
        if 0 < avail <= product.min_quantity:
            Notification.notify_low_stock(product)
        elif avail > product.min_quantity:
            Notification.resolve_low_stock_notifications(product)
        return product


class ProductOperatorSerializer(ModelSerializer):
    """Operator uchun — purchase_price/selling_price yashirin va kiritib bo'lmaydi."""
    quantity_in_stock  = IntegerField(read_only=True)
    reserved_quantity  = IntegerField(read_only=True)
    available_quantity = IntegerField(read_only=True)
    pending_import_quantity = IntegerField(read_only=True)
    stock_status       = SerializerMethodField()
    # category_name      = SerializerMethodField()
    unit_display       = SerializerMethodField()
    origin_display     = SerializerMethodField()
    serial_number      = CharField(required=False, allow_blank=True,
                                   allow_null=True, max_length=255)
    # category           = PrimaryKeyRelatedField(queryset=Category.objects.all())
    quantity            = IntegerField(write_only=True, required=False, min_value=1)
    warehouse_location  = CharField(write_only=True, required=False,
                                    allow_blank=True, max_length=255)

    class Meta:
        model  = Product
        fields = ('id', 'name',
                  # Model funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
                  # 'model',
                  'serial_number', 'barcode', 'source',
                  'origin', 'origin_display', 'unit', 'unit_display',
                  'quantity_in_stock', 'reserved_quantity',
                  'available_quantity', 'pending_import_quantity', 'stock_status', 'quantity',
                  'warehouse_location', 'created_at')
        read_only_fields = ('created_at',)

    def get_stock_status(self, obj):
        return obj.stock_status

    # def get_category_name(self, obj):
    #     return str(obj.category) if obj.category else None

    def get_unit_display(self, obj):
        return obj.get_unit_display()

    def get_origin_display(self, obj):
        return obj.get_origin_display()

    def validate(self, attrs):
        if 'serial_number' in attrs:
            attrs['serial_number'] = normalize_product_serial(attrs['serial_number'])
            # Seriya raqami noyob — takrorlansa 500 emas, tushunarli 400 qaytsin
            if serial_number_is_taken(attrs['serial_number'],
                                      exclude_pk=getattr(self.instance, 'pk', None)):
                raise ValidationError({
                    'serial_number': (f'"{attrs["serial_number"]}" seriya raqami boshqa '
                                      f'mahsulotda band — boshqa raqam kiriting.')})
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


class ProductAccountantSerializer(ProductSerializer):
    """Accountant uchun — narxlar ko'rinadi, mahsulot yaratish/tahrirlash yo'q."""

    class Meta(ProductSerializer.Meta):
        read_only_fields = tuple(
            field for field in ProductSerializer.Meta.fields if field != 'id'
        )


class StockSerializer(ModelSerializer):
    product_name      = SerializerMethodField()
    # Model funksiyasi vaqtincha o'chirilgan — keyinchalik qaytariladi.
    # product_model     = SerializerMethodField()
    min_quantity      = SerializerMethodField()
    stock_status      = SerializerMethodField()
    unit              = SerializerMethodField()
    unit_display      = SerializerMethodField()
    pending_import_quantity = SerializerMethodField()

    class Meta:
        model  = Stock
        fields = ('id', 'product', 'product_name',
                  # 'product_model',
                  'quantity', 'reserved_quantity', 'warehouse_location',
                  'min_quantity', 'stock_status', 'unit', 'unit_display',
                  'pending_import_quantity')
        # reserved_quantity faqat buyurtma (bron) mexanizmi orqali o'zgaradi —
        # qo'lda o'zgartirish order.reserved_qty bilan mosligini buzadi
        read_only_fields = ('reserved_quantity',)

    def get_product_name(self, obj):
        return str(obj.product)

    # def get_product_model(self, obj):
    #     return obj.product.model

    def get_pending_import_quantity(self, obj):
        return obj.product.pending_import_quantity

    def get_min_quantity(self, obj):
        return obj.product.min_quantity

    def get_stock_status(self, obj):
        return obj.product.stock_status

    def get_unit(self, obj):
        return obj.product.unit

    def get_unit_display(self, obj):
        return obj.product.get_unit_display()

    @transaction.atomic
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
        # Qoldiq bron qilingan miqdordan kam bo'lib qolmasin — aks holda
        # mavjud bronlar ombordagi realsiz tovarni "ushlab turadi"
        quantity = attrs.get('quantity',
                             getattr(self.instance, 'quantity', 0))
        reserved = getattr(self.instance, 'reserved_quantity', 0) or 0
        if quantity is not None and quantity < reserved:
            raise ValidationError({
                'quantity': (f'Qoldiq ({quantity}) bron qilingan miqdordan '
                             f'({reserved}) kam bo\'lishi mumkin emas. Avval '
                             'tegishli buyurtmalarni bekor qiling.')})
        return attrs
