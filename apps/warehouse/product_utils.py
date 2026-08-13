from django.utils import timezone

from apps.warehouse.models import Product


def ensure_product_serial_number(serial):
    """Bo'sh bo'lsa IMP-... beradi; band bo'lsa suffix qo'shadi."""
    serial = (serial or '').strip()
    if not serial:
        serial = f'IMP-{timezone.now().strftime("%Y%m%d%H%M%S%f")}'
    base = serial
    counter = 1
    while Product.objects.filter(serial_number=serial).exists():
        serial = f'{base}-{counter}'
        counter += 1
    return serial


def create_import_product(data):
    """Import/zakaz paytida omborga yangi mahsulot qo'shish."""
    return Product.objects.create(
        name=data['name'].strip(),
        serial_number=ensure_product_serial_number(data.get('serial_number')),
        barcode=(data.get('barcode') or '').strip() or None,
        unit=data.get('unit') or 'piece',
        vat_percent=data.get('vat_percent') or 'none',
        purchase_price=data.get('purchase_price'),
        delivery_price=data.get('delivery_price'),
    )
