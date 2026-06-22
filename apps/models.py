from django.db.models import (Model, CharField, ForeignKey, PROTECT, TextField,
                              DateTimeField, PositiveIntegerField)


class Warehouse(Model):
    name = CharField(max_length=255)

    def __str__(self):
        return self.name


class Item(Model):
    name = CharField(max_length=255)
    sku = CharField(max_length=100, unique=True)
    serial_number = CharField(max_length=255, blank=True, null=True)

    warehouse = ForeignKey(
        'apps.Warehouse',
        on_delete=PROTECT,
        related_name='items'
    )

    description = TextField(blank=True, null=True)

    created_at = DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class StockMovement(Model):
    IN = 'IN'
    OUT = 'OUT'

    MOVEMENT_TYPES = (
        (IN, 'Kirim'),
        (OUT, 'Chiqim'),
    )

    item = ForeignKey(
        Item,
        on_delete=PROTECT,
        related_name='movements'
    )

    movement_type = CharField(
        max_length=3,
        choices=MOVEMENT_TYPES
    )

    quantity = PositiveIntegerField()
    comment = TextField(
        blank=True,
        null=True
    )
    created_at = DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.item.name} - {self.movement_type}"
