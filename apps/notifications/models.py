from django.conf import settings
from django.db.models import CharField, TextField, BooleanField, ForeignKey, CASCADE

from apps.common.models import TimeStampedModel


class Notification(TimeStampedModel):
    """Saytdagi (in-app) bildirishnoma — bevosita foydalanuvchiga biriktirilgan."""
    recipient = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE,
                           related_name='notifications')
    title     = CharField(max_length=255)
    message   = TextField()
    is_read   = BooleanField(default=False)

    class Meta:
        db_table = 'notifications_notification'
        ordering = ('-created_at',)
        verbose_name = 'Bildirishnoma'
        verbose_name_plural = 'Bildirishnomalar'

    def __str__(self):
        return f'{self.title} → {self.recipient}'


class TelegramSettings(TimeStampedModel):
    """Singleton — faqat bitta yozuv bo'lishi kerak (pk=1)."""
    bot_token  = CharField(max_length=255)
    chat_id    = CharField(max_length=100)
    is_active  = BooleanField(default=True)
    extra_note = TextField(blank=True, null=True)

    class Meta:
        db_table         = 'notifications_telegramsettings'
        verbose_name     = 'Telegram sozlamalari'
        verbose_name_plural = 'Telegram sozlamalari'

    def __str__(self):
        return f'TelegramSettings (chat: {self.chat_id})'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'bot_token': '', 'chat_id': ''})
        return obj
