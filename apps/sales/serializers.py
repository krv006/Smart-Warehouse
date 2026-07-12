from django.db import transaction
from django.db.models import F
from rest_framework.serializers import (ModelSerializer, Serializer,
                                        ValidationError, DecimalField,
                                        SerializerMethodField, DateField,
                                        CharField, PrimaryKeyRelatedField)

from apps.clients.models import Client
from apps.sales.models import Sale
from apps.warehouse.models import Stock, Product


def _deplete_stock(product, quantity):
    """
    Mahsulot qoldig'ini FIFO (id bo'yicha) tartibida kamaytiradi.
    Faqat BRON QILINMAGAN (quantity - reserved_quantity) qismdan oladi —
    buyurtmalar uchun ajratilgan bron sotuvga ketmaydi.
    Qatorlar qulf ostida qayta tekshiriladi: yetmasa — xato (race-safe).
    """
    remaining = quantity
    stocks = (product.stocks
              .select_for_update()
              .filter(quantity__gt=0)
              .order_by('id'))
    for stock in stocks:
        if remaining <= 0:
            break
        free = stock.quantity - stock.reserved_quantity
        if free <= 0:
            continue
        take = min(free, remaining)
        stock.quantity = F('quantity') - take
        stock.save(update_fields=['quantity'])
        remaining -= take
    if remaining > 0:
        raise ValidationError({
            'quantity': (
                f'"{product.name}" uchun sotish mumkin bo\'lgan qoldiq '
                f'yetarli emas ({remaining} dona yetishmayapti — qoldiq '
                f'boshqa amal bilan band qilingan bo\'lishi mumkin).'
            )
        })


def _restore_stock(product, quantity):
    """
    Sotuv o'chirilganda/kamaytirilganda qoldiqni omborga qaytaradi
    (birinchi lokatsiyaga, FIFO teskarisi emas — hisob umumiy qoldiqda).
    """
    if quantity <= 0:
        return
    stock = product.stocks.select_for_update().order_by('id').first()
    if stock is None:
        product.stocks.create(quantity=quantity, warehouse_location='—')
        return
    stock.quantity = F('quantity') + quantity
    stock.save(update_fields=['quantity'])


class SaleSerializer(ModelSerializer):
    total_amount  = DecimalField(max_digits=14, decimal_places=2, read_only=True)
    profit        = DecimalField(max_digits=14, decimal_places=2, read_only=True, allow_null=True)
    product_name  = SerializerMethodField()
    client_name   = SerializerMethodField()

    class Meta:
        model  = Sale
        fields = ('id', 'product', 'product_name', 'client', 'client_name',
                  'quantity', 'sold_price', 'total_amount', 'profit',
                  'sold_to', 'destination', 'sold_date', 'comment', 'created_at')
        read_only_fields = ('created_at',)

    def get_product_name(self, obj):
        return str(obj.product)

    def get_client_name(self, obj):
        return str(obj.client) if obj.client else None

    def validate_quantity(self, value):
        if value <= 0:
            raise ValidationError("Miqdor noldan katta bo'lishi kerak.")
        return value

    def validate(self, attrs):
        product   = attrs.get('product', getattr(self.instance, 'product', None))
        quantity  = attrs.get('quantity', getattr(self.instance, 'quantity', 0))
        # Bron qilinmagan (available) qoldiqqa qarab tekshirish
        available = product.available_quantity if product else 0
        # Tahrirda: shu sotuvning eski miqdori allaqachon ombordan ayirilgan —
        # mahsulot o'zgarmagan bo'lsa, u qaytariladigan hisobga qo'shiladi
        if self.instance and product and self.instance.product_id == product.id:
            available += self.instance.quantity
        if quantity > available:
            reserved = product.reserved_quantity if product else 0
            raise ValidationError({
                'quantity': (
                    f'"{product.name}" uchun sotish mumkin bo\'lgan qoldiq yetarli emas. '
                    f'Jami: {product.quantity_in_stock}, bron: {reserved}, '
                    f'mavjud: {available}, so\'ralgan: {quantity}.'
                )
            })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        sale = super().create(validated_data)
        _deplete_stock(sale.product, sale.quantity)
        return sale

    @transaction.atomic
    def update(self, instance, validated_data):
        """
        Tahrirda ombor qoldig'i mos tuzatiladi: eski miqdor qaytariladi,
        yangi miqdor (yangi mahsulotdan bo'lsa — undan) qayta ayiriladi.
        """
        old_product  = instance.product
        old_quantity = instance.quantity
        sale = super().update(instance, validated_data)
        if sale.product_id != old_product.id or sale.quantity != old_quantity:
            _restore_stock(old_product, old_quantity)
            _deplete_stock(sale.product, sale.quantity)
        return sale


class SaleOperatorSerializer(SaleSerializer):
    """
    Operator uchun — sotuv narxi, jami summa va foyda YASHIRIN.
    Biznes qoidasi: operator sotuv summalarini/narxlarni ko'rmaydi.
    sold_price yozishда kerak, shuning uchun write_only qilinadi.
    """
    sold_price = DecimalField(max_digits=14, decimal_places=2, write_only=True)

    class Meta(SaleSerializer.Meta):
        fields = ('id', 'product', 'product_name', 'client', 'client_name',
                  'quantity', 'sold_price',
                  'sold_to', 'destination', 'sold_date', 'comment', 'created_at')


class SaleItemSerializer(Serializer):
    """Bulk savdo ichidagi bitta mahsulot qatori."""
    product    = PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity   = DecimalField(max_digits=12, decimal_places=0, min_value=1)
    sold_price = DecimalField(max_digits=14, decimal_places=2)
    comment    = CharField(required=False, allow_blank=True, allow_null=True)


class SaleBulkCreateSerializer(Serializer):
    """
    Bir vaqtda bir nechta mahsulot savdosi.
    Har bir mahsulot alohida Sale yozuvi bo'ladi (bitta client/sana/manzil ostida).

    Namuna:
    {
      "client": "<uuid>",
      "sold_to": "Aliyev Vohid",
      "destination": "Toshkent",
      "sold_date": "2026-07-02",
      "items": [
        { "product": 12, "quantity": 4, "sold_price": "3900000" },
        { "product": 7,  "quantity": 2, "sold_price": "1200000" }
      ]
    }
    """
    client      = PrimaryKeyRelatedField(queryset=Client.objects.all(),
                                         required=False, allow_null=True)
    sold_to     = CharField(required=False, allow_blank=True, allow_null=True)
    destination = CharField(required=False, allow_blank=True, allow_null=True)
    sold_date   = DateField()
    items       = SaleItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise ValidationError('Kamida bitta mahsulot kiritilishi kerak.')
        # Har bir qatorda available_quantity ni tekshirish.
        # Bitta mahsulot bir necha marta kelsa — yig'indini hisobga olamiz.
        needed = {}
        for item in value:
            needed[item['product']] = needed.get(item['product'], 0) + int(item['quantity'])
        errors = []
        for product, qty in needed.items():
            available = product.available_quantity
            if qty > available:
                errors.append(
                    f'"{product.name}" — sotish mumkin bo\'lgan qoldiq yetarli emas '
                    f'(mavjud: {available}, so\'ralgan: {qty}).'
                )
        if errors:
            raise ValidationError(errors)
        return value

    @transaction.atomic
    def create(self, validated_data):
        client      = validated_data.get('client')
        sold_to     = validated_data.get('sold_to')
        destination = validated_data.get('destination')
        sold_date   = validated_data['sold_date']
        items       = validated_data['items']

        created = []
        for item in items:
            sale = Sale.objects.create(
                product=item['product'],
                client=client,
                quantity=int(item['quantity']),
                sold_price=item['sold_price'],
                sold_to=sold_to,
                destination=destination,
                sold_date=sold_date,
                comment=item.get('comment'),
            )
            _deplete_stock(sale.product, sale.quantity)
            created.append(sale)
        return created

    def to_representation(self, instance):
        return {'sales': SaleSerializer(instance, many=True).data}
