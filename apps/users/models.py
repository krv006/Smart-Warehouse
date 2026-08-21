from django.contrib.auth.models import AbstractUser
from django.db.models import CharField, BooleanField


class User(AbstractUser):
    OPERATOR    = 'OPERATOR'
    ACCOUNTANT  = 'ACCOUNTANT'
    MANAGEMENT  = 'MANAGEMENT'
    SALES       = 'SALES'

    ROLES = (
        (OPERATOR,   'Operator (Ishchi)'),
        (ACCOUNTANT, 'Accountant (Buxgalter)'),
        (MANAGEMENT, 'Management (Boshqaruv)'),
        (SALES,      'Sales (Sotuvchi)'),
    )

    role             = CharField(max_length=20, choices=ROLES, default=OPERATOR)
    phone            = CharField(max_length=20, blank=True, null=True)
    telegram_id      = CharField(max_length=50, blank=True, null=True)
    can_view_clients = BooleanField(default=False)

    class Meta:
        db_table = 'users_user'
        verbose_name = 'Foydalanuvchi'
        verbose_name_plural = 'Foydalanuvchilar'

    @property
    def is_management(self):
        return self.role == self.MANAGEMENT or self.is_superuser

    @property
    def is_operator(self):
        # Operator (Buxgalter deb ham yuritiladi) — to'liq dostup: Management
        # bilan bir xil huquqqa ega, faqat status o'zgartirishlar (Zakaz/Order
        # holati) Management tomonidan tasdiqlanishi kerak (is_pending_approval).
        return self.role == self.OPERATOR or self.is_superuser

    @property
    def is_accountant(self):
        # Admin (Management) va Buxgalter (Accountant) bir xil imkoniyatlarga
        # ega — faqat Buxgalter kiritgan o'zgarish Adminga tasdiqlash uchun
        # ketadi (bu view/serializer darajasida hal qilinadi, is_accountant
        # o'zi to'liq huquq beradi).
        return self.role == self.ACCOUNTANT or self.is_superuser

    @property
    def is_sales(self):
        return self.role == self.SALES or self.is_superuser

    @property
    def requires_change_approval(self):
        """Buxgalter (ACCOUNTANT) qilgan o'zgarishlar Admin tasdig'iga muhtoj —
        Management/Operator/superuser/Sales uchun False."""
        return self.role == self.ACCOUNTANT and not self.is_superuser
