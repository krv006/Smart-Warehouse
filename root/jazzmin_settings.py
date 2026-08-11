# Jazzmin admin-panel sozlamalari.
# MUHIM: model manzillari "app_label.Model" ko'rinishida bo'ladi.
# Bu loyihada app label'lar — apps.py dagi name'ning oxirgi bo'lagi:
# users, warehouse, sales, cash, clients, expenses, orders, notifications.

JAZZMIN_SETTINGS = {
    # ── Sarlavha ─────────────────────────────────────────────────────────
    "site_title":   "Sklad Boshqaruvi",
    "site_header":  "Sklad & Savdo",
    "site_brand":   "Sklad & Savdo",
    "welcome_sign": "Xush kelibsiz!",
    "copyright":    "Sklad & Savdo © 2026",

    "site_logo":         None,
    "login_logo":        None,
    "login_logo_dark":   None,
    "site_icon":         None,
    "site_logo_classes": None,

    # ── Global qidiruv (navbar) ──────────────────────────────────────────
    "search_model": [
        "warehouse.Product",
        "orders.Order",
        "orders.Zakaz",
        "sales.Sale",
        "clients.Client",
    ],

    # ── Top navbar havolalar ─────────────────────────────────────────────
    "topmenu_links": [
        {"name": "Bosh sahifa", "url": "admin:index",
         "permissions": ["auth.view_user"]},
        {"model": "orders.Order"},
        {"model": "orders.Zakaz"},
        {"model": "warehouse.Product"},
        {"model": "cash.Payment"},
        {"name": "Swagger API", "url": "/",           "new_window": True},
        {"name": "ReDoc",       "url": "/api/redoc/", "new_window": True},
    ],

    "usermenu_links": [
        {"name": "Swagger API", "url": "/", "new_window": True,
         "icon": "fas fa-code"},
    ],

    "user_avatar": None,

    # ── Sidebar ──────────────────────────────────────────────────────────
    "show_sidebar":        True,
    "navigation_expanded": False,

    "hide_apps":   [],
    "hide_models": [],

    # Biznes oqimi tartibida: buyurtma → ombor → sotuv → kassa → mijoz →
    # rasxod → bildirishnoma → foydalanuvchi → tizim
    "order_with_respect_to": [
        "orders",
        "orders.Order",
        "orders.Zakaz",
        "orders.ProductContract",
        "warehouse",
        "warehouse.Product",
        "warehouse.Stock",
        "warehouse.Category",
        "sales",
        "cash",
        "clients",
        "expenses",
        "notifications",
        "users",
        "auth",
        "django_celery_beat",
    ],

    "icons": {
        # Buyurtmalar / Bron
        "orders":                 "fas fa-clipboard-list",
        "orders.order":           "fas fa-file-signature",
        "orders.zakaz":           "fas fa-truck-loading",
        "orders.productcontract": "fas fa-file-contract",
        # Ombor
        "warehouse":              "fas fa-warehouse",
        "warehouse.product":      "fas fa-box-open",
        "warehouse.stock":        "fas fa-cubes",
        "warehouse.category":     "fas fa-sitemap",
        # Sotuv / Kassa
        "sales":                  "fas fa-cash-register",
        "sales.sale":             "fas fa-cash-register",
        "cash":                   "fas fa-money-bill-wave",
        "cash.payment":           "fas fa-money-check-alt",
        # Mijozlar / Rasxodlar
        "clients":                "fas fa-address-book",
        "clients.client":         "fas fa-address-card",
        "expenses":               "fas fa-wallet",
        "expenses.expense":       "fas fa-receipt",
        "expenses.expensetype":   "fas fa-tags",
        "expenses.expensesubtype": "fas fa-tag",
        # Bildirishnomalar
        "notifications":                  "fas fa-bell",
        "notifications.notification":     "fas fa-bell",
        "notifications.telegramsettings": "fab fa-telegram",
        # Foydalanuvchilar / tizim
        "users":       "fas fa-users-cog",
        "users.user":  "fas fa-user",
        "auth":        "fas fa-shield-alt",
        "auth.group":  "fas fa-users",
    },
    "default_icon_parents":  "fas fa-folder",
    "default_icon_children": "fas fa-circle",

    # ── Modal o'chirilgan (singan rasm muammosi yo'q) ─────────────────────
    "related_modal_active": False,

    # ── Custom CSS/JS ─────────────────────────────────────────────────────
    "custom_css": "admin/css/custom.css",
    "custom_js":  None,

    "use_google_fonts_cdn": True,
    "show_ui_builder":      False,

    # ── Form ko'rinishi ───────────────────────────────────────────────────
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "warehouse.product": "horizontal_tabs",
        "sales.sale":        "horizontal_tabs",
        "orders.order":      "horizontal_tabs",
        "orders.zakaz":      "horizontal_tabs",
        "users.user":        "collapsible",
    },

    "language_chooser": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text":  False,
    "footer_small_text":  True,
    "body_small_text":    False,
    "brand_small_text":   False,

    # ── Tema: har doim LIGHT ──────────────────────────────────────────────
    "theme":           "default",
    "dark_mode_theme": None,

    # ── Rang ─────────────────────────────────────────────────────────────
    "brand_colour":    "navbar-primary",
    "accent":          "accent-primary",

    # ── Navbar: oq, yengil ───────────────────────────────────────────────
    "navbar":          "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed":    True,

    # ── Sidebar: to'q ko'k, kompakt ──────────────────────────────────────
    "sidebar":                   "sidebar-dark-primary",
    "sidebar_fixed":             True,
    "sidebar_nav_small_text":    False,
    "sidebar_disable_expand":    False,
    "sidebar_nav_child_indent":  True,
    "sidebar_nav_compact_style": True,
    "sidebar_nav_legacy_style":  False,
    "sidebar_nav_flat_style":    True,

    # ── Layout ───────────────────────────────────────────────────────────
    "layout_boxed":  False,
    "footer_fixed":  False,

    "actions_sticky_top": True,

    "button_classes": {
        "primary":   "btn-primary",
        "secondary": "btn-secondary",
        "info":      "btn-info",
        "warning":   "btn-warning",
        "danger":    "btn-danger",
        "success":   "btn-success",
    },
}
