"""
Excel export helpers. Each function returns an HttpResponse with an .xlsx file.
"""
import io
from datetime import date

import openpyxl
from django.http import HttpResponse
from openpyxl.styles import Font, PatternFill, Alignment

HEADER_FONT  = Font(bold=True, color='FFFFFF')
HEADER_FILL  = PatternFill('solid', fgColor='2E75B6')
CENTER       = Alignment(horizontal='center', vertical='center')


def _create_workbook(title: str):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title
    return wb, ws


def _write_header(ws, columns: list[str]):
    ws.append(columns)
    for cell in ws[1]:
        cell.font      = HEADER_FONT
        cell.fill      = HEADER_FILL
        cell.alignment = CENTER


def _response(wb, filename: str) -> HttpResponse:
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def export_sales(queryset) -> HttpResponse:
    wb, ws = _create_workbook('Sotuvlar')
    _write_header(ws, [
        '№', 'Mahsulot', 'Kategoriya', 'Miqdor', 'Sotuv narxi',
        'Jami summa', 'Qayerga ketdi', 'Mijoz', 'Sana', 'Izoh',
    ])
    for i, sale in enumerate(queryset, 1):
        ws.append([
            i,
            str(sale.product),
            str(sale.product.category) if sale.product.category else '',
            sale.quantity,
            float(sale.sold_price),
            float(sale.sold_price * sale.quantity),
            sale.destination or '',
            sale.sold_to or '',
            sale.sold_date.isoformat() if sale.sold_date else '',
            sale.comment or '',
        ])
    today = date.today().isoformat()
    return _response(wb, f'sotuvlar_{today}.xlsx')


def export_stock(queryset) -> HttpResponse:
    from decimal import Decimal
    from apps.warehouse.models import VatPercent

    wb, ws = _create_workbook('Ombor holati')
    _write_header(ws, [
        '№', 'Mahsulot nomi', 'Kategoriya', 'Seriya raqami', 'Shtrix kod',
        'O\'lchov birligi', 'Qoldiq', 'Bron', 'Mavjud', 'Omborxona',
        'Kelish narxi', 'Sotuv narxi', 'Yetkazish narxi', 'QQS %',
        'QQS miqdori (qoldiq)', 'Jami (qoldiq×sotuv)', 'Minimal qoldiq',
        'Holat', 'Manba',
    ])
    for i, stock in enumerate(queryset, 1):
        product = stock.product
        qty = stock.quantity or 0
        reserved = stock.reserved_quantity or 0
        available = qty - reserved
        sell = product.selling_price
        delivery = product.delivery_price
        vat_rate = VatPercent.rate(product.vat_percent)
        vat_label = dict(VatPercent.choices).get(product.vat_percent, product.vat_percent or '')
        line_base = (Decimal(sell or 0) * Decimal(qty)) if sell is not None else Decimal('0')
        vat_amount = (line_base * vat_rate / Decimal('100')).quantize(Decimal('0.01')) if sell else ''
        total = (line_base + vat_amount).quantize(Decimal('0.01')) if sell else ''
        ws.append([
            i,
            product.name,
            str(product.category) if product.category else '',
            product.serial_number,
            product.barcode or '',
            product.get_unit_display(),
            qty,
            reserved,
            available,
            stock.warehouse_location,
            float(product.purchase_price) if product.purchase_price is not None else '',
            float(sell) if sell is not None else '',
            float(delivery) if delivery is not None else '',
            vat_label,
            float(vat_amount) if vat_amount != '' else '',
            float(total) if total != '' else '',
            product.min_quantity,
            product.stock_status,
            product.source or '',
        ])
    today = date.today().isoformat()
    return _response(wb, f'ombor_{today}.xlsx')


def export_expenses(queryset) -> HttpResponse:
    wb, ws = _create_workbook('Rasxodlar')
    _write_header(ws, [
        '№', 'Toifa', 'Tur', 'Summa', 'Valyuta',
        'Sana', 'Mas\'ul', 'Izoh',
    ])
    for i, exp in enumerate(queryset, 1):
        ws.append([
            i,
            str(exp.expense_type),
            str(exp.sub_type) if exp.sub_type else '',
            float(exp.amount),
            exp.currency,
            exp.date.isoformat(),
            str(exp.responsible) if exp.responsible else '',
            exp.comment or '',
        ])
    today = date.today().isoformat()
    return _response(wb, f'rasxodlar_{today}.xlsx')


def export_payments(queryset) -> HttpResponse:
    wb, ws = _create_workbook('Kassa')
    _write_header(ws, [
        '№', 'Manba', 'Mahsulot', 'Mijoz',
        'Jami summa', 'Komissiya (15%)', 'Toʻlangan',
        'Qoldiq', 'Valyuta', 'Toʻlov muddati', 'Status',
    ])
    for i, pay in enumerate(queryset, 1):
        remaining = pay.total_amount - pay.paid_amount
        # To'lov sotuvdan YOKI buyurtmadan bo'ladi — sale None bo'lishi mumkin
        if pay.sale_id:
            source  = f'Sotuv #{pay.sale_id}'
            product = str(pay.sale.product)
        elif pay.order_id:
            source  = f'Buyurtma #{pay.order_id}'
            product = ', '.join(str(item.product)
                                for item in pay.order.items.all())
        else:
            source, product = '', ''
        ws.append([
            i,
            source,
            product,
            str(pay.client) if pay.client else '',
            float(pay.total_amount),
            float(pay.commission),
            float(pay.paid_amount),
            float(remaining),
            pay.currency,
            pay.due_date.isoformat() if pay.due_date else '',
            pay.get_status_display(),
        ])
    today = date.today().isoformat()
    return _response(wb, f'kassa_{today}.xlsx')
