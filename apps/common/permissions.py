from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOperator(BasePermission):
    """Faqat Operator yoki superuser."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and getattr(request.user, 'is_operator', False))


class IsAccountant(BasePermission):
    """Faqat Accountant yoki superuser."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and getattr(request.user, 'is_accountant', False))


class IsManagement(BasePermission):
    """Faqat Management yoki superuser."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and getattr(request.user, 'is_management', False))


class IsOperatorOrReadOnly(BasePermission):
    """O'qish — hammaga, yozish — faqat Operator."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return getattr(request.user, 'is_operator', False)


class IsOperatorOrManagement(BasePermission):
    """Operator yoki Management — ombor qoldig'ini siljitadigan amallar uchun
    (buyurtmani yetkazish/bekor qilish, zakaz ochish). Accountant kirolmaydi."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return (getattr(request.user, 'is_operator', False)
                or getattr(request.user, 'is_management', False))


class IsAccountantOrManagement(BasePermission):
    """Accountant yoki Management."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return (getattr(request.user, 'is_accountant', False)
                or getattr(request.user, 'is_management', False))


class IsAccountantOrReadOnly(BasePermission):
    """O'qish — hammaga, yozish — Accountant."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return getattr(request.user, 'is_accountant', False)


class CanViewClients(BasePermission):
    """Faqat can_view_clients ruxsati bor foydalanuvchilar."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and getattr(request.user, 'can_view_clients', False))
