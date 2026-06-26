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
    wb, ws = _create_workbook('Ombor holati')
    _write_header(ws, [
        '№', 'Mahsulot', 'Kategoriya', 'Serial №',
        'Qoldiq (dona)', 'Omborxona', 'Narxi (sotib olish)',
    ])
    for i, stock in enumerate(queryset, 1):
        ws.append([
            i,
            str(stock.product),
            str(stock.product.category) if stock.product.category else '',
            stock.product.serial_number,
            stock.quantity,
            stock.warehouse_location,
            float(stock.product.purchase_price),
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
        '№', 'Sotuv ID', 'Mahsulot', 'Mijoz',
        'Jami summa', 'Komissiya (15%)', 'Toʻlangan',
        'Qoldiq', 'Valyuta', 'Toʻlov muddati', 'Status',
    ])
    for i, pay in enumerate(queryset, 1):
        remaining = pay.total_amount - pay.paid_amount
        ws.append([
            i,
            pay.sale_id,
            str(pay.sale.product),
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
