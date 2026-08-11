from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import (api_view, authentication_classes,
                                       permission_classes, throttle_classes)
from rest_framework.mixins import (DestroyModelMixin, ListModelMixin,
                                   RetrieveModelMixin, UpdateModelMixin)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.viewsets import GenericViewSet

from apps.common.permissions import IsManagement
from apps.users.models import User
from apps.users.serializers import (
    LoginSerializer,
    RegisterOperatorSerializer,
    UserSerializer,
    user_session_payload,
)


class LoginRateThrottle(AnonRateThrottle):
    """
    Login brute-force himoyasi — IP bo'yicha 10/min (drf_settings dagi
    'login' rate). MUHIM: ScopedRateThrottle EMAS — u FBV'da view'dan
    throttle_scope qidirib topolmay, tekshiruvsiz o'tkazib yuborardi.
    """
    scope = 'login'


@extend_schema(summary="Login — JWT token olish", tags=["Auth"],
               request=LoginSerializer, responses={200: LoginSerializer}, auth=[])
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    from apps.notifications.models import Notification
    Notification.sync_missing_price_for_user(serializer.validated_data['user'])

    return Response(serializer.data)


@extend_schema(summary="Yangi foydalanuvchi yaratish (Management)",
               tags=["Auth"], request=RegisterOperatorSerializer,
               responses={201: RegisterOperatorSerializer})
@api_view(['POST'])
@permission_classes([IsManagement])
def register_user(request):
    serializer = RegisterOperatorSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(summary="Joriy foydalanuvchi va UI ruxsatlari", tags=["Auth"])
@api_view(['GET'])
def me(request):
    return Response(user_session_payload(request.user))


@extend_schema(tags=["Users"])
class UserViewSet(ListModelMixin, RetrieveModelMixin,
                  UpdateModelMixin, DestroyModelMixin, GenericViewSet):
    """
    Yaratish YO'Q — bu yerdan yaratilgan user parolsiz qolib ketardi
    (UserSerializer'da parol maydoni yo'q). Yangi user faqat
    /auth/register/ (RegisterOperatorSerializer, parol validatsiyasi bilan).
    """
    serializer_class = UserSerializer
    permission_classes = (IsManagement,)
    search_fields = ('username', 'first_name', 'last_name')
    filterset_fields = ('role', 'is_active')

    def get_queryset(self):
        # Superuserlar boshqaruv ro'yxatida ko'rinmaydi va tegib bo'lmaydi
        # (faqat superuserning o'zi hammasini ko'radi)
        qs = User.objects.all().order_by('-date_joined')
        if not self.request.user.is_superuser:
            qs = qs.filter(is_superuser=False)
        return qs

    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.is_superuser and not self.request.user.is_superuser:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Superuser hisobini o\'zgartirib bo\'lmaydi.')
        serializer.save()

    def perform_destroy(self, instance):
        from rest_framework.exceptions import PermissionDenied
        if instance.is_superuser and not self.request.user.is_superuser:
            raise PermissionDenied('Superuser hisobini o\'chirib bo\'lmaydi.')
        if instance.pk == self.request.user.pk:
            raise PermissionDenied('O\'z hisobingizni o\'chirib bo\'lmaydi.')
        instance.delete()
