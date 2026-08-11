from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.views import login, me, register_user, UserViewSet

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')

urlpatterns = [
    path('login/',            login,                      name='login'),
    path('me/',               me,                         name='me'),
    path('token/refresh/',    TokenRefreshView.as_view(), name='token-refresh'),
    path('register/',         register_user,              name='register-user'),
    *router.urls,
]
