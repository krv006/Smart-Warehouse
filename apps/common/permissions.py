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


class IsManagementOnly(BasePermission):
    """Faqat Management (yozish/amal) — superuser ham ruxsatli."""
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


class IsOperatorOrManagementWrite(BasePermission):
    """O'qish — hammaga autentifikatsiyalangan, yozish — Operator yoki Management."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return (getattr(request.user, 'is_operator', False)
                or getattr(request.user, 'is_management', False))


class IsOperatorOrManagement(BasePermission):
    """Operator, Accountant yoki Management — ombor qoldig'ini siljitadigan
    amallar uchun (buyurtmani yetkazish/bekor qilish, zakaz ochish). Admin va
    Buxgalter bir xil huquqqa ega — Buxgalter tomonidan kiritilgan
    o'zgarishlar view darajasida (`requires_change_approval`) tasdiqlash
    navbatiga tushadi, bu yerda faqat KIM AMALGA OSHIRA OLADI tekshiriladi."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return (getattr(request.user, 'is_operator', False)
                or getattr(request.user, 'is_accountant', False)
                or getattr(request.user, 'is_management', False))


class IsFullAccessOrSales(BasePermission):
    """To'liq huquqli rollar (Operator/Accountant/Management) yoki Sales.
    Ko'rish/yaratish hammasiga ochiq — obyekt darajasidagi cheklov (Sales
    faqat o'zinikini) view/queryset ichida amalga oshiriladi."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return bool(getattr(request.user, 'is_operator', False)
                    or getattr(request.user, 'is_accountant', False)
                    or getattr(request.user, 'is_management', False)
                    or getattr(request.user, 'is_sales', False))


class IsSales(BasePermission):
    """Faqat Sales (yoki superuser)."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and getattr(request.user, 'is_sales', False))


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


class IsAccountantWithManagementRead(BasePermission):
    """O'qish — Operator (faqat ko'rish), Accountant/Management; yozish — Accountant/Management."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return (getattr(request.user, 'is_operator', False)
                    or getattr(request.user, 'is_accountant', False)
                    or getattr(request.user, 'is_management', False))
        return (getattr(request.user, 'is_accountant', False)
                or getattr(request.user, 'is_management', False))


class CanViewClients(BasePermission):
    """can_view_clients ruxsati berilgan foydalanuvchilar, yoki to'liq huquqli
    rollar (Operator/Accountant/Management), yoki Sales (mijozlar bazasi bilan
    ishlaydi — item 6: yangi mijoz qo'shadi, faqat o'zinikini ko'radi —
    ob'ekt darajasidagi cheklov ClientViewSet.get_queryset ichida)."""
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return bool(getattr(user, 'can_view_clients', False)
                    or getattr(user, 'is_operator', False)
                    or getattr(user, 'is_accountant', False)
                    or getattr(user, 'is_management', False)
                    or getattr(user, 'is_sales', False))
