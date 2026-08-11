from django.core.management.base import BaseCommand

from apps.notifications.models import Notification
from apps.orders.models import Zakaz
from django.utils import timezone


class Command(BaseCommand):
    help = 'Kutilgan sanasi o\'tgan importlar uchun kechikish bildirishnomalarini yuboradi'

    def handle(self, *args, **options):
        today = timezone.localdate()
        overdue = Zakaz.objects.filter(
            expected_date__lt=today,
        ).exclude(
            status__in=(Zakaz.RECEIVED, Zakaz.CANCELLED),
        ).select_related('product')

        count = 0
        for zakaz in overdue:
            Notification.notify_delayed_import(zakaz)
            count += 1
        self.stdout.write(self.style.SUCCESS(f'{count} ta kechikkan import tekshirildi.'))
