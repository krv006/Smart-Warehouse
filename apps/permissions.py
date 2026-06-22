from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOperatorOrReadOnly(BasePermission):
    """
    Yozish (kirim/sotuv) — faqat Operator (yoki superuser).
    O'qish — autentifikatsiyadan o'tgan har qanday foydalanuvchi.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return getattr(request.user, 'is_operator', False)


class IsManagement(BasePermission):
    """Hisobot va analitika — faqat Management (yoki superuser)."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'is_management', False)
        )
