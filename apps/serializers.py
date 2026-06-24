from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import F
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from rest_framework.serializers import (ModelSerializer, Serializer,
                                        ValidationError, IntegerField,
                                        DecimalField, CharField,
                                        SerializerMethodField)
from rest_framework_simplejwt.tokens import RefreshToken

from apps.models import User, Product, Stock, Sale, Category


class LoginSerializer(Serializer):
    username = CharField()
    password = CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        user = authenticate(username=attrs['username'], password=attrs['password'])
        if not user:
            raise ValidationError('Login yoki parol noto\'g\'ri.')
        if not user.is_active:
            raise ValidationError('Foydalanuvchi faol emas.')
        attrs['user'] = user
        return attrs

    def to_representation(self, instance):
        user = self.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return {
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id':       user.id,
                'username': user.username,
                'role':     user.role,
            },
        }


class RegisterOperatorSerializer(ModelSerializer):
    password = CharField(write_only=True, min_length=8,
                         style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'first_name', 'last_name')
        read_only_fields = ('id',)

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data, role=User.OPERATOR)
        user.set_password(password)
        user.save()
        return user


class CategorySerializer(ModelSerializer):
    children = SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'parent', 'children')

    def get_children(self, obj):
        return CategorySerializer(obj.children.all(), many=True).data


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Laptop kirim namunasi",
            value={
                "name": "MacBook Pro",
                "model": "M3 Pro 14\"",
                "serial_number": "C02XK1JFJGH5",
                "purchase_price": "12500000.00",
            },
            request_only=True,
        )
    ]
)
class ProductSerializer(ModelSerializer):
    quantity_in_stock = IntegerField(read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Product
        fields = (
            'id', 'category', 'category_id', 'name', 'model', 'serial_number',
            'purchase_price', 'quantity_in_stock', 'created_at',
        )
        read_only_fields = ('created_at',)


class ProductOperatorSerializer(ProductSerializer):
    class Meta(ProductSerializer.Meta):
        fields = (
            'id', 'category', 'category_id', 'name', 'model', 'serial_number',
            'quantity_in_stock', 'created_at',
        )


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


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Sotuv namunasi",
            value={
                "product": 1,
                "sold_price": "14000000.00",
                "quantity": 1,
                "sold_to": "Alibek Karimov",
                "sold_date": "2024-06-22",
                "comment": "Naqd to'lov",
            },
            request_only=True,
        )
    ]
)
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
