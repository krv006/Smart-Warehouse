from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

import requests
import urllib3

from django.utils import timezone

from apps.cash.models import ExchangeRate


INFINBANK_EXCHANGE_RATES_URL = 'https://www.infinbank.com/uz/private/exchange-rates/'


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
        raise ExchangeRateFetchError('Infinbank kurs qiymati topilmadi.')
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ExchangeRateFetchError(f'Infinbank kurs qiymati noto‘g‘ri: {value}') from exc


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


def sync_today_usd_rate():
    today = timezone.localdate()
    manual_rate = (
        ExchangeRate.objects
        .filter(currency=ExchangeRate.USD, rate_date=today, manual_override=True)
        .order_by('-created_at')
        .first()
    )
    if manual_rate:
        return manual_rate, False

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
