from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.serializers import (ModelSerializer, Serializer,
                                        ValidationError, CharField)
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User


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
            'user': {
                'id':       user.id,
                'username': user.username,
                'role':     user.role,
                'can_view_clients': user.can_view_clients,
            },
        }


class RegisterOperatorSerializer(ModelSerializer):
    password = CharField(write_only=True, min_length=8,
                         style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'first_name', 'last_name',
                  'role', 'phone', 'telegram_id')
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
