import os
from pathlib import Path

from dotenv import load_dotenv

from root.drf_settings import *
from root.jazzmin_settings import JAZZMIN_SETTINGS, JAZZMIN_UI_TWEAKS

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# SECRET_KEY — production'da (.env) MAJBURIY. Ishonchsiz kalit bilan
# istalgan kishi yaroqli JWT yasab, superuser nomidan kira olardi.
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        # Faqat lokal dev uchun — production'da hech qachon ishlatilmaydi
        SECRET_KEY = 'django-insecure-dev-only-CHANGE-ME-in-env'
    else:
        raise RuntimeError(
            'SECRET_KEY environment o\'zgaruvchisi kiritilishi shart '
            '(DEBUG=False). .env fayliga kuchli tasodifiy kalit qo\'ying.'
        )

# ALLOWED_HOSTS — .env dan vergul bilan ajratilgan ro'yxat
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()
]
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['*'] if DEBUG else ['localhost', '127.0.0.1']

# CORS — .env dagi CORS_ALLOWED_ORIGINS (vergul bilan) whitelist qilinadi.
# Credentials bilan '*' xavfli, shuning uchun aniq domenlar talab qilinadi.
_cors_origins = [
    o.strip() for o in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if o.strip()
]
if _cors_origins:
    CORS_ALLOWED_ORIGINS   = _cors_origins
    CORS_ALLOW_ALL_ORIGINS = False
else:
    # Whitelist bo'sh bo'lsa: dev'da hammaga ochiq, prod'da hech kimga
    CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept', 'authorization', 'content-type',
    'origin', 'x-csrftoken', 'x-requested-with',
]
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']

# CSRF — trusted originlar (session-auth admin panel uchun)
CSRF_TRUSTED_ORIGINS = _cors_origins or []

# Production xavfsizlik sozlamalari (DEBUG=False da yoqiladi)
if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER   = True
    SESSION_COOKIE_SECURE       = True
    CSRF_COOKIE_SECURE          = True
    SECURE_HSTS_SECONDS         = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER     = ('HTTP_X_FORWARDED_PROTO', 'https')
    X_FRAME_OPTIONS             = 'DENY'

DJANGO_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'django_filters',
    'drf_spectacular',
    'mptt',
    'django_celery_beat',
]

LOCAL_APPS = [
    'apps.common',
    'apps.users',
    'apps.warehouse',
    'apps.sales',
    'apps.expenses',
    'apps.cash',
    'apps.clients',
    'apps.reports',
    'apps.notifications',
    'apps.orders',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'root.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'root.wsgi.application'

if os.environ.get('DB_ENGINE') == 'postgres':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'warehouse'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'uz'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Fernet encryption key (generate: from cryptography.fernet import Fernet; Fernet.generate_key())
FERNET_KEY = os.environ.get('FERNET_KEY', '')

# ── Celery ──────────────────────────────────────────────────────────────────
CELERY_BROKER_URL        = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND    = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_TIMEZONE          = 'Asia/Tashkent'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT   = 30 * 60
