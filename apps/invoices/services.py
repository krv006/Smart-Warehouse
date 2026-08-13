"""Buyurtma (SK) hujjatlarini mahsulot shartnomalari reestriga yozish."""
from apps.invoices.models import DocumentType, ElectronicInvoice, InvoiceLineItem
from apps.orders.models import ProductContract, register_contract
from apps.warehouse.models import Product


def _invoice_asos(invoice: ElectronicInvoice) -> str:
    doc_label = invoice.get_document_type_display()
    client = str(invoice.client) if invoice.client else '—'
    parts = [f'{doc_label} №{invoice.contract_number or "—"}', f'mijoz: {client}']
    if invoice.comment:
        parts.append(invoice.comment.strip())
    return ' — '.join(parts)


def _resolve_line_product(line: InvoiceLineItem):
    if line.product_id:
        return line.product
    code = (line.identification_code or '').strip()
    if code:
        product = Product.objects.filter(serial_number=code).first()
        if product:
            return product
    name = (line.product_name or '').strip()
    if name:
        return Product.objects.filter(name__iexact=name).first()
    return None


def sync_invoice_contract_registry(invoice: ElectronicInvoice, *, created: bool, user=None):
    """
    Har bir mahsulot qatori uchun ProductContract reestriga yozuv qo'shadi.
    Ombordagi mahsulot bog'langan yoki nomi/kodi mos keladigan qatorlar yoziladi.
    """
    if invoice.document_type != DocumentType.CONTRACT_SK:
        return []

    source_type = (ProductContract.INVOICE_CREATED if created
                   else ProductContract.INVOICE_EDITED)
    asos = _invoice_asos(invoice)
    faktura = invoice.name or invoice.get_document_type_display()
    entries = []

    for line in invoice.lines.all():
        product = _resolve_line_product(line)
        if not product:
            continue
        entries.append(register_contract(
            product,
            source_type,
            contract_number=invoice.contract_number,
            contract_date=invoice.contract_date,
            asos=asos,
            faktura=faktura,
            invoice=invoice,
            user=user,
        ))
    return entries
