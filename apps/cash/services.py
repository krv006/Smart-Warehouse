import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

import requests
import urllib3

from django.utils import timezone

from apps.cash.models import ExchangeRate


INFINBANK_EXCHANGE_RATES_URL = 'https://www.infinbank.com/uz/private/exchange-rates/'
BANKXIZMATLARI_RATES_URL = 'https://bankxizmatlari.uz/uz/rates/'

# InFinBank + eng mashhur 5 ta bank (bankxizmatlari.uz data-bank kodlari).
POPULAR_BANK_CODES = (
    '053',  # InFinBank
    '002',  # O'zmilliybank
    '049',  # Kapitalbank
    '012',  # Hamkorbank
    '006',  # Xalq banki
    '004',  # Agrobank
)

POPULAR_BANK_NAMES = {
    '053': 'InFinBank',
    '002': "O'zmilliybank",
    '049': 'Kapitalbank',
    '012': 'Hamkorbank',
    '006': 'Xalq banki',
    '004': 'Agrobank',
}

BANKXIZMATLARI_ITEM_RE = re.compile(
    r'<div class="item js-element-item"([^>]+)>.*?'
    r'<div class="item__header--name">([^<]+)</div>.*?'
    r'<span class="item__update--text">([^<]+)</span>',
    re.DOTALL | re.IGNORECASE,
)

_market_rates_cache = {'data': None, 'fetched_at': None}
MARKET_RATES_TTL = timedelta(hours=1)


class ExchangeRateFetchError(Exception):
    pass


class RatesTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self._row = []
        elif tag in {'td', 'th'} and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in {'td', 'th'} and self._row is not None and self._cell is not None:
            text = ' '.join(''.join(self._cell).split())
            self._row.append(text)
            self._cell = None
        elif tag == 'tr' and self._row is not None:
            if any(cell for cell in self._row):
                self.rows.append(self._row)
            self._row = None
            self._cell = None


def parse_decimal(value):
    cleaned = value.replace('\xa0', ' ').replace(' ', '').replace(',', '.')
    cleaned = ''.join(char for char in cleaned if char.isdigit() or char in '.-')
    if not cleaned:
        raise ExchangeRateFetchError('Kurs qiymati topilmadi.')
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ExchangeRateFetchError(f'Kurs qiymati noto‘g‘ri: {value}') from exc


def parse_optional_decimal(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned or cleaned == '0':
        return None
    try:
        return parse_decimal(cleaned)
    except ExchangeRateFetchError:
        return None


def _attr_value(attrs, name):
    match = re.search(rf'{re.escape(name)}="([^"]*)"', attrs)
    return match.group(1) if match else ''


def parse_bankxizmatlari_usd_rates(html):
    """bankxizmatlari.uz sahifasidan mashhur banklar USD sotib olish/sotish kurslari."""
    by_code = {}
    for attrs, raw_name, updated_text in BANKXIZMATLARI_ITEM_RE.findall(html):
        code = _attr_value(attrs, 'data-bank')
        if code not in POPULAR_BANK_CODES:
            continue
        buy_rate = parse_optional_decimal(_attr_value(attrs, 'data-usd-buy-bank'))
        sell_rate = parse_optional_decimal(_attr_value(attrs, 'data-usd-sale-bank'))
        if buy_rate is None and sell_rate is None:
            continue
        name = POPULAR_BANK_NAMES.get(code) or raw_name.strip()
        by_code[code] = {
            'code': code,
            'name': name,
            'buy_rate': buy_rate,
            'sell_rate': sell_rate,
            'updated_at': updated_text.strip(),
            'source': 'bankxizmatlari',
        }

    rates = [by_code[code] for code in POPULAR_BANK_CODES if code in by_code]
    if not rates:
        raise ExchangeRateFetchError('Bankxizmatlari.uz sahifasida bank kurslari topilmadi.')
    return rates


def _request_bankxizmatlari(verify=True):
    return requests.get(
        BANKXIZMATLARI_RATES_URL,
        headers={
            'User-Agent': 'Mozilla/5.0 (compatible; SmartWarehouse/1.0)',
            'Accept-Language': 'uz,en;q=0.8',
        },
        timeout=20,
        verify=verify,
    )


def fetch_bankxizmatlari_usd_rates():
    try:
        response = _request_bankxizmatlari()
        response.raise_for_status()
    except requests.exceptions.SSLError:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        try:
            response = _request_bankxizmatlari(verify=False)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ExchangeRateFetchError('Bankxizmatlari.uz sahifasiga ulanishda xatolik.') from exc
    except requests.RequestException as exc:
        raise ExchangeRateFetchError('Bankxizmatlari.uz sahifasiga ulanishda xatolik.') from exc
    return parse_bankxizmatlari_usd_rates(response.text)


def get_cached_market_usd_rates():
    return _market_rates_cache.get('data')


def get_market_usd_rates(*, force=False):
    now = timezone.now()
    cached_at = _market_rates_cache.get('fetched_at')
    if (
        not force
        and _market_rates_cache.get('data') is not None
        and cached_at is not None
        and now - cached_at < MARKET_RATES_TTL
    ):
        return _market_rates_cache['data']

    try:
        rates = fetch_bankxizmatlari_usd_rates()
    except ExchangeRateFetchError:
        if _market_rates_cache.get('data') is not None:
            return _market_rates_cache['data']
        raise

    payload = {
        'source': 'bankxizmatlari',
        'source_url': BANKXIZMATLARI_RATES_URL,
        'fetched_at': now.isoformat(),
        'banks': [
            {
                **bank,
                'buy_rate': str(bank['buy_rate']) if bank['buy_rate'] is not None else None,
                'sell_rate': str(bank['sell_rate']) if bank['sell_rate'] is not None else None,
            }
            for bank in rates
        ],
    }
    _market_rates_cache['data'] = payload
    _market_rates_cache['fetched_at'] = now
    return payload


def parse_infinbank_usd_mb_rate(html):
    parser = RatesTableParser()
    parser.feed(html)

    header_row = next((row for row in parser.rows if 'USD' in row), None)
    if not header_row:
        raise ExchangeRateFetchError('Infinbank sahifasida USD ustuni topilmadi.')

    usd_index = header_row.index('USD')
    mb_row = next((row for row in parser.rows if row and row[0].strip().lower() == 'mb kurs'), None)
    if not mb_row or len(mb_row) <= usd_index:
        raise ExchangeRateFetchError('Infinbank sahifasida USD MB kursi topilmadi.')

    return parse_decimal(mb_row[usd_index])


def fetch_infinbank_usd_mb_rate():
    try:
        response = _request_infinbank()
        response.raise_for_status()
    except requests.exceptions.SSLError:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        try:
            response = _request_infinbank(verify=False)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ExchangeRateFetchError('Infinbank sahifasiga ulanishda xatolik.') from exc
    except requests.RequestException as exc:
        raise ExchangeRateFetchError('Infinbank sahifasiga ulanishda xatolik.') from exc
    return parse_infinbank_usd_mb_rate(response.text)


def _request_infinbank(verify=True):
    return requests.get(
        INFINBANK_EXCHANGE_RATES_URL,
        headers={
            'User-Agent': 'Mozilla/5.0 (compatible; SmartWarehouse/1.0)',
            'Accept-Language': 'uz,en;q=0.8',
        },
        timeout=15,
        verify=verify,
    )


def sync_today_usd_rate(*, force=False):
    """Infinbank kursini yangilaydi — qo'lda kurs alohida saqlanadi va bloklamaydi."""
    today = timezone.localdate()
    mb_rate = fetch_infinbank_usd_mb_rate()
    rate = (
        ExchangeRate.objects
        .filter(currency=ExchangeRate.USD, rate_date=today, manual_override=False)
        .order_by('-created_at')
        .first()
    )

    if rate is None:
        rate = ExchangeRate(currency=ExchangeRate.USD, rate_date=today)

    rate.mb_rate = mb_rate
    rate.buy_rate = mb_rate
    rate.sell_rate = mb_rate
    rate.source = 'infinbank'
    rate.manual_override = False
    rate.note = f'{INFINBANK_EXCHANGE_RATES_URL} dan avtomatik olingan MB kurs'
    rate.save()
    return rate, True


def get_today_rate(*, manual):
    today = timezone.localdate()
    return (
        ExchangeRate.objects
        .filter(currency=ExchangeRate.USD, rate_date=today, manual_override=manual)
        .order_by('-created_at')
        .first()
    )


def get_bank_from_market(code):
    payload = get_cached_market_usd_rates()
    if payload is None:
        try:
            payload = get_market_usd_rates()
        except ExchangeRateFetchError:
            return None
    for bank in payload.get('banks', []):
        if bank.get('code') == code:
            return bank
    return None


def resolve_bank_rate(code, side):
    bank = get_bank_from_market(code)
    if not bank:
        return None
    key = 'sell_rate' if side == 'sell' else 'buy_rate'
    raw = bank.get(key)
    if raw is None:
        return None
    return Decimal(str(raw))


def get_active_rate_info():
    from apps.cash.models import ExchangeRateSettings

    settings = ExchangeRateSettings.get_settings()
    manual = get_today_rate(manual=True)

    if settings.preferred_rate_source == ExchangeRateSettings.MANUAL and manual:
        return {
            'mb_rate': manual.mb_rate,
            'source': ExchangeRateSettings.MANUAL,
            'active_source': ExchangeRateSettings.MANUAL,
            'record': manual,
        }

    if (
        settings.preferred_rate_source == ExchangeRateSettings.BANK
        and settings.preferred_bank_code
    ):
        bank = get_bank_from_market(settings.preferred_bank_code)
        side = settings.preferred_bank_side or ExchangeRateSettings.SELL
        rate = resolve_bank_rate(settings.preferred_bank_code, side)
        if bank and rate is not None:
            return {
                'mb_rate': rate,
                'source': ExchangeRateSettings.BANK,
                'active_source': ExchangeRateSettings.BANK,
                'active_bank_code': settings.preferred_bank_code,
                'active_bank_name': bank.get('name') or settings.preferred_bank_code,
                'active_bank_side': side,
                'record': None,
            }

    auto = get_today_rate(manual=False) or ExchangeRate.get_latest(ExchangeRate.USD)
    return {
        'mb_rate': auto.mb_rate if auto else Decimal('0'),
        'source': ExchangeRateSettings.INFINBANK,
        'active_source': ExchangeRateSettings.INFINBANK,
        'record': auto,
    }


def get_active_rate_record():
    info = get_active_rate_info()
    return info.get('record'), info['active_source']


def get_active_mb_rate():
    return get_active_rate_info()['mb_rate']
