from celery import shared_task

from apps.cash.services import sync_today_usd_rate


@shared_task
def refresh_infinbank_usd_rate():
    rate, updated = sync_today_usd_rate()
    return {
        'id': rate.pk,
        'currency': rate.currency,
        'mb_rate': str(rate.mb_rate),
        'rate_date': rate.rate_date.isoformat(),
        'updated': updated,
        'manual_override': rate.manual_override,
    }
