from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsManagement
from apps.users.models import User
from apps.users.serializers import LoginSerializer, RegisterOperatorSerializer, UserSerializer


@extend_schema(summary="Login — JWT token olish", tags=["Auth"],
               request=LoginSerializer, responses={200: LoginSerializer}, auth=[])
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
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


@extend_schema(tags=["Users"])
class UserViewSet(ModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = (IsManagement,)
    search_fields = ('username', 'first_name', 'last_name')
    filterset_fields = ('role', 'is_active')
