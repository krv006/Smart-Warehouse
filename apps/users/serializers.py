from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.serializers import (ModelSerializer, Serializer,
                                        ValidationError, CharField)
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User


def user_abilities(user):
    is_management = bool(getattr(user, 'is_management', False))
    is_operator = bool(getattr(user, 'is_operator', False))
    is_accountant = bool(getattr(user, 'is_accountant', False))
    can_view_clients = bool(getattr(user, 'can_view_clients', False))

    return {
        'dashboard': is_accountant or is_management,
        'orders_view': True,
        'orders_manage': is_operator or is_management,
        'warehouse_view': True,
        'warehouse_manage': is_operator or is_management,
        'prices_view': is_accountant or is_management,
        'prices_manage': is_management,
        'clients_view': can_view_clients,
        'clients_manage': can_view_clients,
        'sales_view': True,
        'sales_manage': is_operator,
        'cash_view': True,
        'cash_manage': is_accountant or is_management,
        'expenses_view': True,
        'expenses_manage': is_accountant or is_management,
        'reports_view': is_accountant or is_management,
        'notifications_view': True,
        'procurement_view': True,
        'procurement_manage': is_operator or is_management,
        'contracts_view': True,
        'categories_view': True,
        'stocks_view': True,
        'users_view': is_management,
        'users_manage': is_management,
    }


def user_session_payload(user):
    return {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'can_view_clients': user.can_view_clients,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'is_management': bool(getattr(user, 'is_management', False)),
        'abilities': user_abilities(user),
    }


class LoginSerializer(Serializer):
    username = CharField()
    password = CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        user = authenticate(username=attrs['username'], password=attrs['password'])
        if not user:
            raise ValidationError("Login yoki parol noto'g'ri.")
        if not user.is_active:
            raise ValidationError('Foydalanuvchi faol emas.')
        attrs['user'] = user
        return attrs

    def to_representation(self, instance):
        user = self.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return {
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
            'user': user_session_payload(user),
        }


class RegisterOperatorSerializer(ModelSerializer):
    password = CharField(write_only=True, min_length=8,
                         style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'first_name', 'last_name',
                  'role', 'phone', 'telegram_id', 'can_view_clients')
        read_only_fields = ('id',)

    def validate_password(self, value):
        # Django parol validatorlari (murakkablik, umumiy parollar va h.k.)
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise ValidationError(list(e.messages))
        return value

    def validate_role(self, value):
        # Faqat ruxsat etilgan rollar — superuser/staff bu yerdan berilmaydi
        if value not in dict(User.ROLES):
            raise ValidationError('Noto\'g\'ri rol.')
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name',
                  'role', 'phone', 'telegram_id', 'can_view_clients',
                  'is_active', 'date_joined')
        read_only_fields = ('id', 'date_joined')
