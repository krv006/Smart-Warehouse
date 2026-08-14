from apps.warehouse.models import Product, ProductOrigin


def normalize_product_serial(serial):
    """Seriya raqamini tozalaydi. Bo'sh bo'lsa None — AVTOMATIK yaratilmaydi."""
    serial = (serial or '').strip()
    return serial or None


def create_import_product(data, origin=ProductOrigin.IMPORT):
    """Import/zakaz/buyurtma paytida omborga yangi mahsulot qo'shish."""
    return Product.objects.create(
        name=data['name'].strip(),
        category=data.get('category'),
        serial_number=normalize_product_serial(data.get('serial_number')),
        barcode=(data.get('barcode') or '').strip() or None,
        unit=data.get('unit') or 'piece',
        vat_percent=data.get('vat_percent') or 'none',
        purchase_price=data.get('purchase_price'),
        selling_price=data.get('selling_price'),
        delivery_price=data.get('delivery_price'),
        origin=origin,
    )


def find_product(name=None, serial_number=None, barcode=None):
    """Nom / seriya raqami / shtrix kod bo'yicha ombordagi mahsulotni topadi."""
    serial = normalize_product_serial(serial_number)
    if serial:
        product = Product.objects.filter(serial_number=serial).first()
        if product:
            return product
    code = (barcode or '').strip()
    if code:
        product = Product.objects.filter(barcode=code).first()
        if product:
            return product
    label = (name or '').strip()
    if label:
        return Product.objects.filter(name__iexact=label).first()
    return None
