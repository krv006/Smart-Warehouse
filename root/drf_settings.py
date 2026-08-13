REST_FRAMEWORK = {
    # TZ: role-based access — standart talab autentifikatsiya,
    # aniq rol tekshiruvi har bir view'da (IsOperatorOrReadOnly / IsManagement).
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated"
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    # Brute-force / DoS himoyasi — faqat autentifikatsiyalangan foydalanuvchi
    # (AnonRateThrottle olib tashlandi: token/refresh va boshqa ochiq endpointlar
    # 60/min chekloviga tushib, UI «Request was throttled» xatosini berardi).
    # Login alohida LoginRateThrottle bilan himoyalangan (apps/users/views.py).
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        "anon":  "60/min",     # LoginRateThrottle scope (login endpoint)
        "user":  "5000/min",   # tizimga kirgan foydalanuvchi
        "login": "10/min",     # login urinishlari (parol brute-force ga qarshi)
    },
}

from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "AUTH_HEADER_TYPES": ("Bearer",),
    # Har refresh'da yangi refresh-token beriladi, eskisi blacklist'ga
    # tushadi — o'g'irlangan token 30 kun yashamaydi
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Sklad & Savdo API",
    "DESCRIPTION": (
        "Tovarlarni hisobga olish, ombor (sklad) boshqaruvi va sotuv "
        "jarayonlarini nazorat qilish uchun REST API.\n\n"
        "**Rollar:**\n"
        "- `OPERATOR` — tovar kirimi, qoldiq va sotuvlarni kiritadi\n"
        "- `MANAGEMENT` — hisobot, foyda va analitikani ko'radi"
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Swagger/schema anonim foydalanuvchiga ko'rinmasin (API recon himoyasi)
    "SERVE_PUBLIC": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
    "CONTACT": {"email": "admin@warehouse.uz"},
    "LICENSE": {"name": "Private"},
    # Swagger UI sozlamalari
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
    },
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    "SECURITY": [{"BearerAuth": []}],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}
