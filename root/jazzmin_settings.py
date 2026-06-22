JAZZMIN_SETTINGS = {
    # ── Sarlavha ─────────────────────────────────────────────────────────
    "site_title":   "Sklad Boshqaruvi",
    "site_header":  "Sklad & Savdo",
    "site_brand":   "Sklad & Savdo",
    "welcome_sign": "Xush kelibsiz!",
    "copyright":    "Sklad & Savdo © 2024",

    "site_logo":         None,
    "login_logo":        None,
    "login_logo_dark":   None,
    "site_icon":         None,
    "site_logo_classes": None,

    # ── Qidiruv ──────────────────────────────────────────────────────────
    "search_model": [
        "apps.Product",
        "apps.Stock",
        "apps.Sale",
        "apps.User",
    ],

    # ── Top navbar havolalar (screenshot dagi kabi: Home, Support...) ────
    "topmenu_links": [
        {"name": "Home",        "url": "admin:index",  "permissions": ["auth.view_user"]},
        {"name": "Swagger API", "url": "/",            "new_window": True},
        {"name": "ReDoc",       "url": "/api/redoc/",  "new_window": True},
        {"model": "apps.Product"},
        {"model": "apps.Sale"},
    ],

    "usermenu_links": [
        {"name": "Swagger API", "url": "/", "new_window": True, "icon": "fas fa-code"},
    ],

    # ── Foydalanuvchi avatari ─────────────────────────────────────────────
    "user_avatar": None,

    # ── Sidebar ──────────────────────────────────────────────────────────
    "show_sidebar":        True,
    "navigation_expanded": False,      # <- screenshot dagi kabi yopiq (mini) holat

    "hide_apps":   [],
    "hide_models": [],

    "order_with_respect_to": [
        "apps",
        "apps.User",
        "apps.Product",
        "apps.Stock",
        "apps.Sale",
        "auth",
    ],

    "icons": {
        "apps":         "fas fa-warehouse",
        "apps.user":    "fas fa-users-cog",
        "apps.product": "fas fa-box-open",
        "apps.stock":   "fas fa-cubes",
        "apps.sale":    "fas fa-cash-register",
        "auth":         "fas fa-shield-alt",
        "auth.group":   "fas fa-users",
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
        "apps.product": "horizontal_tabs",
        "apps.sale":    "horizontal_tabs",
        "auth.user":    "collapsible",
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

    # ── Navbar: oq, yengil (screenshot dagi kabi) ────────────────────────
    "navbar":          "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed":    True,

    # ── Sidebar: to'q ko'k, mini holat ───────────────────────────────────
    "sidebar":                   "sidebar-dark-primary",
    "sidebar_fixed":             True,
    "sidebar_nav_small_text":    False,
    "sidebar_disable_expand":    False,
    "sidebar_nav_child_indent":  True,
    "sidebar_nav_compact_style": True,   # <- compact (screenshot dagi kabi)
    "sidebar_nav_legacy_style":  False,
    "sidebar_nav_flat_style":    True,   # <- flat, toza ko'rinish

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
