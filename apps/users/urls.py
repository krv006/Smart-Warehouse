from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.users.views import (SafeTokenRefreshView, login, me, register_user,
                              UserViewSet)

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')

urlpatterns = [
    path('login/',            login,                          name='login'),
    path('me/',               me,                             name='me'),
    path('token/refresh/',    SafeTokenRefreshView.as_view(), name='token-refresh'),
    path('register/',         register_user,                  name='register-user'),
    *router.urls,
]
