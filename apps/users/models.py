from django.contrib.auth.models import AbstractUser
from django.db.models import CharField, BooleanField


class User(AbstractUser):
    OPERATOR    = 'OPERATOR'
    ACCOUNTANT  = 'ACCOUNTANT'
    MANAGEMENT  = 'MANAGEMENT'

    ROLES = (
        (OPERATOR,   'Operator (Ishchi)'),
        (ACCOUNTANT, 'Accountant (Buxgalter)'),
        (MANAGEMENT, 'Management (Boshqaruv)'),
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
        return self.role == self.OPERATOR or self.is_superuser

    @property
    def is_accountant(self):
        return self.role == self.ACCOUNTANT or self.is_superuser
