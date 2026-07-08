from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.orders'
    verbose_name = 'Buyurtmalar / Bron'

    def ready(self):
        # Kassa ↔ buyurtma avtomatik sinxron signallari
        from apps.orders import signals  # noqa: F401
