"""
Celery tasks for Telegram notifications.

Scheduled in config/celery.py via CELERY_BEAT_SCHEDULE:
  - check_overdue_payments: runs every day at 09:00
  - daily_backup_notification: runs every day at 22:00 (after backup cron)
"""
import logging

import requests
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


def _send_telegram(text: str) -> bool:
    from apps.notifications.models import TelegramSettings
    cfg = TelegramSettings.get_settings()
    if not cfg.is_active or not cfg.bot_token or not cfg.chat_id:
        logger.warning('TelegramSettings not configured or inactive.')
        return False
    url = f'https://api.telegram.org/bot{cfg.bot_token}/sendMessage'
    resp = requests.post(url, json={
        'chat_id':    cfg.chat_id,
        'text':       text,
        'parse_mode': 'HTML',
    }, timeout=10)
    if not resp.ok:
        logger.error('Telegram xatosi: %s', resp.text)
        return False
    return True


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def check_overdue_payments(self):
    """Muddati o'tgan to'lovlar haqida Telegram'ga xabar yuboradi."""
    from apps.cash.models import Payment
    today   = timezone.now().date()
    overdue = Payment.objects.filter(
        status__in=(Payment.PENDING, Payment.PARTIAL),
        due_date__lt=today,
    ).select_related('sale__product', 'client')

    if not overdue.exists():
        return 'No overdue payments.'

    lines = [f'⚠️ <b>Muddati o\'tgan to\'lovlar</b> ({today}):\n']
    for pay in overdue[:20]:
        client = str(pay.client) if pay.client else '—'
        remaining = pay.total_amount - pay.paid_amount
        lines.append(
            f'• {pay.sale.product} | {client} | '
            f'qoldiq: <b>{remaining:,.0f} {pay.currency}</b> | '
            f'muddati: {pay.due_date}'
        )
    if overdue.count() > 20:
        lines.append(f'… va yana {overdue.count() - 20} ta')

    _send_telegram('\n'.join(lines))
    return f'{overdue.count()} overdue payment(s) notified.'


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def send_backup_notification(self, success: bool, filepath: str = ''):
    """DB backup natijasini Telegram'ga yuboradi (backup script chaqiradi)."""
    if success:
        text = f'✅ <b>DB backup muvaffaqiyatli</b>\n📁 {filepath}'
    else:
        text = '❌ <b>DB backup XATOSI!</b> Tekshiring.'
    _send_telegram(text)
