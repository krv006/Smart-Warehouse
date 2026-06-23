from django.contrib.auth.models import AbstractUser
from django.db.models import (Model, CharField, ForeignKey, PROTECT, CASCADE,
                              TextField, DateTimeField, DateField,
                              PositiveIntegerField, DecimalField, Sum, F,
                              SET_NULL)
from mptt.models import MPTTModel, TreeForeignKey


class User(AbstractUser):
    """Tizim foydalanuvchisi. TZ: 2 ta rol — Operator va Management."""
    OPERATOR = 'OPERATOR'
    MANAGEMENT = 'MANAGEMENT'

    ROLES = (
        (OPERATOR, 'Operator (Ishchi)'),
        (MANAGEMENT, 'Management (Boshqaruv)'),
    )

    role = CharField(max_length=20, choices=ROLES, default=OPERATOR)

    @property
    def is_management(self):
        return self.role == self.MANAGEMENT or self.is_superuser

    @property
    def is_operator(self):
        return self.role == self.OPERATOR or self.is_superuser


class Category(MPTTModel):
    """Daraxt ko'rinishidagi tovar kategoriyasi (MPTT)."""
    name = CharField(max_length=255)
    parent = TreeForeignKey(
        'self', on_delete=CASCADE,
        null=True, blank=True,
        related_name='children',
    )

    class MPTTMeta:
        order_insertion_by = ('name',)

    class Meta:
        verbose_name = 'Kategoriya'
        verbose_name_plural = 'Kategoriyalar'

    def __str__(self):
        return self.name


class Product(Model):
    """TZ: Products — id, name, model, serial_number, purchase_price, created_at."""
    category = TreeForeignKey(
        Category, on_delete=SET_NULL,
        null=True, blank=True,
        related_name='products',
    )
    name = CharField(max_length=255)
    model = CharField(max_length=255, blank=True, null=True)
    serial_number = CharField(max_length=255, unique=True)
    purchase_price = DecimalField(max_digits=14, decimal_places=2)
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Product'
        verbose_name_plural = 'Products'

    def __str__(self):
        return f'{self.name} ({self.serial_number})'

    @property
    def quantity_in_stock(self):
        """Barcha lokatsiyalardagi umumiy qoldiq."""
        return self.stocks.aggregate(total=Sum('quantity'))['total'] or 0


class Stock(Model):
    """TZ: Stock — product_id, quantity, warehouse_location."""
    product = ForeignKey(Product, on_delete=CASCADE, related_name='stocks')
    quantity = PositiveIntegerField(default=0)
    warehouse_location = CharField(max_length=255)

    class Meta:
        ordering = ('product', 'warehouse_location')
        verbose_name = 'Stock'
        verbose_name_plural = 'Stocks'
        unique_together = ('product', 'warehouse_location')

    def __str__(self):
        return f'{self.product.name} @ {self.warehouse_location}: {self.quantity}'


class Sale(Model):
    """TZ: Sales — id, product_id, sold_price, sold_date, sold_to, quantity."""
    product = ForeignKey(Product, on_delete=PROTECT, related_name='sales')
    sold_price = DecimalField(max_digits=14, decimal_places=2,
                              help_text='Birlik uchun sotuv narxi')
    quantity = PositiveIntegerField()
    sold_to = CharField(max_length=255, blank=True, null=True)
    sold_date = DateField()
    comment = TextField(blank=True, null=True)
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-sold_date', '-created_at')
        verbose_name = 'Sale'
        verbose_name_plural = 'Sales'

    def __str__(self):
        return f'{self.product.name} x{self.quantity} -> {self.sold_to or "-"}'

    @property
    def total_amount(self):
        """Umumiy sotuv summasi."""
        return self.sold_price * self.quantity

    @property
    def profit(self):
        """Foyda = (sotuv narxi - olish narxi) * miqdor."""
        return (self.sold_price - self.product.purchase_price) * self.quantity
