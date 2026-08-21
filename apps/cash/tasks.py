from celery import shared_task

from apps.cash.models import ExchangeRateSettings
from apps.cash.services import ExchangeRateFetchError, sync_today_rate


def _rate_payload(rate, updated):
    return {
        'id': rate.pk,
        'currency': rate.currency,
        'mb_rate': str(rate.mb_rate),
        'rate_date': rate.rate_date.isoformat(),
        'updated': updated,
        'manual_override': rate.manual_override,
    }


@shared_task
def refresh_infinbank_usd_rate():
    if not ExchangeRateSettings.get_settings().auto_fetch_enabled:
        return {'skipped': True, 'reason': 'auto_fetch_disabled'}
    rate, updated = sync_today_rate(currency='USD')
    return _rate_payload(rate, updated)


@shared_task
def refresh_infinbank_eur_rate():
    """EUR — Infinbank sahifasida ustun bo'lmasa xato jim yutiladi (USD kabi
    majburiy emas, kassa EUR balansi kursisiz ham ishlayveradi)."""
    if not ExchangeRateSettings.get_settings().auto_fetch_enabled:
        return {'skipped': True, 'reason': 'auto_fetch_disabled'}
    try:
        rate, updated = sync_today_rate(currency='EUR')
    except ExchangeRateFetchError as exc:
        return {'skipped': True, 'reason': str(exc)}
    return _rate_payload(rate, updated)
