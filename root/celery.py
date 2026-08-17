import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'root.settings')

app = Celery('warehouse_erp')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'check-overdue-payments-daily': {
        'task':     'apps.notifications.tasks.check_overdue_payments',
        # Regressiya: butun son (32400) crontab EMAS — Celery buni "har
        # 32400 soniyada" (taxminan 9 soatda bir marta, beat ishga
        # tushgan vaqtdan boshlab siljib boradi) deb tushunadi, "har kuni
        # 09:00 UTC" DEGANI EMAS. To'g'ri kunlik vaqt uchun crontab kerak.
        'schedule': crontab(hour=9, minute=0),  # har kuni 09:00 UTC (14:00 Toshkent)
    },
    'check-delayed-imports-hourly': {
        'task': 'apps.notifications.tasks.check_delayed_imports',
        'schedule': 3600,
    },
    'refresh-infinbank-usd-rate-hourly': {
        'task': 'apps.cash.tasks.refresh_infinbank_usd_rate',
        'schedule': 3600,
    },
}
