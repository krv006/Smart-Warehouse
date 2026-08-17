from decimal import Decimal

from django.db.models import Q, Sum

from apps.cash.models import Payment, PaymentTransaction
from apps.expenses.models import Expense


def _payment_source(payment):
    if payment.order_id:
        return 'order'
    if payment.sale_id:
        return 'sale'
    return 'other'


def build_ledger_entries(search=None, source=None, kind=None,
                         date_from=None, date_to=None):
    entries = []

    tx_qs = (
        PaymentTransaction.objects
        .select_related(
            'payment', 'payment__sale__product', 'payment__order',
            'payment__client', 'received_by',
        )
        .filter(payment__zakaz__isnull=True)
        .order_by('-created_at')
    )

    if search:
        tx_qs = tx_qs.filter(
            Q(payment__comment__icontains=search)
            | Q(payment__client__company_name__icontains=search)
            | Q(payment__order__contract_number__icontains=search)
            | Q(payment__sale__product__name__icontains=search)
            | Q(comment__icontains=search)
        )
    if date_from:
        tx_qs = tx_qs.filter(created_at__date__gte=date_from)
    if date_to:
        tx_qs = tx_qs.filter(created_at__date__lte=date_to)

    for tx in tx_qs:
        payment = tx.payment
        src = _payment_source(payment)
        if source and src != source:
            continue
        if kind and kind != 'in':
            continue
        label = payment.comment or ''
        if src == 'sale' and payment.sale_id:
            label = label or f'Sotuv #{payment.sale_id}'
        elif src == 'order' and payment.order_id:
            label = label or f'Buyurtma #{payment.order_id}'
        entries.append({
            'id': f'in-{tx.pk}',
            'kind': 'in',
            'source': src,
            'amount': str(tx.amount),
            'currency': payment.currency,
            'label': label,
            'client_name': str(payment.client) if payment.client_id else None,
            'date': tx.created_at.date().isoformat(),
            'created_at': tx.created_at.isoformat(),
            'payment_id': payment.pk,
            'remaining': str(payment.remaining_amount),
            'status': payment.status,
        })

    exp_qs = (
        Expense.objects
        .select_related('zakaz__product', 'expense_type')
        .order_by('-date', '-created_at')
    )

    if search:
        exp_qs = exp_qs.filter(
            Q(comment__icontains=search)
            | Q(zakaz__supplier__icontains=search)
            | Q(zakaz__product__name__icontains=search)
            | Q(expense_type__name__icontains=search)
        )
    if date_from:
        exp_qs = exp_qs.filter(date__gte=date_from)
    if date_to:
        exp_qs = exp_qs.filter(date__lte=date_to)

    for exp in exp_qs:
        zakaz = exp.zakaz
        # zakaz/invoice-ga bog'liq chiqim — import; qolgan barcha rasxod
        # turlari (ofis, transport, oylik, boshqa...) — expense
        src = 'import' if (exp.zakaz_id or exp.invoice_id) else 'expense'
        if source and src != source:
            continue
        if kind and kind != 'out':
            continue
        entries.append({
            'id': f'out-{exp.pk}',
            'kind': 'out',
            'source': src,
            'expense_type': exp.expense_type.code if exp.expense_type_id else None,
            'amount': str(exp.amount),
            'currency': exp.currency,
            'label': exp.comment or (f'Import #{zakaz.pk}' if zakaz else exp.expense_type.name),
            'client_name': zakaz.supplier if zakaz else None,
            'date': exp.date.isoformat() if exp.date else None,
            'created_at': exp.created_at.isoformat() if exp.created_at else None,
            'zakaz_id': zakaz.pk if zakaz else None,
        })

    entries.sort(key=lambda row: row.get('created_at') or '', reverse=True)
    return entries


def ledger_totals():
    in_uzs = (
        PaymentTransaction.objects
        .filter(payment__zakaz__isnull=True, payment__currency=Payment.UZS)
        .aggregate(s=Sum('amount'))['s'] or Decimal('0')
    )
    in_usd = (
        PaymentTransaction.objects
        .filter(payment__zakaz__isnull=True, payment__currency=Payment.USD)
        .aggregate(s=Sum('amount'))['s'] or Decimal('0')
    )
    out_import_uzs = (
        Expense.objects
        .filter(Q(zakaz__isnull=False) | Q(invoice__isnull=False), currency=Expense.UZS)
        .aggregate(s=Sum('amount'))['s'] or Decimal('0')
    )
    out_import_usd = (
        Expense.objects
        .filter(Q(zakaz__isnull=False) | Q(invoice__isnull=False), currency=Expense.USD)
        .aggregate(s=Sum('amount'))['s'] or Decimal('0')
    )
    out_uzs = (
        Expense.objects
        .filter(currency=Expense.UZS)
        .aggregate(s=Sum('amount'))['s'] or Decimal('0')
    )
    out_usd = (
        Expense.objects
        .filter(currency=Expense.USD)
        .aggregate(s=Sum('amount'))['s'] or Decimal('0')
    )
    return {
        'sum_in_uzs': in_uzs,
        'sum_in_usd': in_usd,
        # Faqat import (zakaz/faktura) chiqimi — eski maydonlar, moslik uchun
        'sum_import_uzs': out_import_uzs,
        'sum_import_usd': out_import_usd,
        # Barcha rasxodlar (import + ofis/transport/oylik/...)
        'sum_out_uzs': out_uzs,
        'sum_out_usd': out_usd,
        # Kassa umumiy balansi — BARCHA chiqimlar hisobga olingan holda
        'net_balance_uzs': in_uzs - out_uzs,
        'net_balance_usd': in_usd - out_usd,
    }
