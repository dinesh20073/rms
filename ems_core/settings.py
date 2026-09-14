import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent


# ==========================================================================
# Environment Helpers
# ==========================================================================

def get_env_str(key, default=''):
    val = os.getenv(key)
    return val if val is not None and val != '' else default

def get_env_bool(key, default=True):
    val = os.getenv(key)
    if val is None or val == '':
        return default
    return str(val).strip().lower() in ('true', '1', 'yes', 't')

def get_env_int(key, default=587):
    val = os.getenv(key)
    if val is not None and str(val).strip().isdigit():
        return int(str(val).strip())
    return default


# ==========================================================================
# Core Settings
# ==========================================================================

SECRET_KEY = get_env_str('DJANGO_SECRET_KEY', 'django-insecure-ems-super-secret-key-2026-v1-production-ready')
DEBUG = get_env_bool('DJANGO_DEBUG', True)

# Public Customer-Facing and Admin Dashboard Base URLs
PUBLIC_WEB_URL = get_env_str('PUBLIC_WEB_URL', 'https://nizhalcommunity.in').rstrip('/')
ADMIN_WEB_URL = get_env_str('ADMIN_WEB_URL', 'https://admin.nizhalcommunity.in').rstrip('/')

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '.vercel.app',
    'admin-nizhal-community.vercel.app',
    'admin.nizhalcommunity.in',
    'www.admin.nizhalcommunity.in',
    'nizhalcommunity.in',
    'www.nizhalcommunity.in',
    '.nizhalcommunity.in',
]
# Allow all hosts in development
if DEBUG:
    ALLOWED_HOSTS = ['*']


# ==========================================================================
# Installed Apps
# ==========================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'rest_framework',
    
    # Core EMS Apps
    'apps.tenants',
    'apps.events',
    'apps.forms_builder',
    'apps.registrations',
    'apps.payments',
    'apps.verification',
    'apps.notifications',
    'apps.audit',
    'apps.api_v1',
    'apps.dashboard',
]


# ==========================================================================
# Middleware
# ==========================================================================

MIDDLEWARE = [
    'ems_core.middleware.RewriteHostPreserveMiddleware',
    'django.middleware.security.SecurityMiddleware',
]
try:
    import whitenoise
    MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')
except ImportError:
    pass
MIDDLEWARE.extend([
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.dashboard.middleware.BankSessionSecurityMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
])

ROOT_URLCONF = 'ems_core.urls'


# ==========================================================================
# Templates — Clean configuration with optional caching in production
# ==========================================================================

# Choose loaders based on DEBUG mode: cached in production for performance
_template_loaders = [
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    'ems_core.template_loader.EmbeddedTemplateLoader',
]
if not DEBUG:
    _template_loaders = [
        ('django.template.loaders.cached.Loader', _template_loaders),
    ]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'ems_core' / 'templates',
            Path('/var/task/templates'),
            Path('/var/task/ems_core/templates'),
            Path(__file__).resolve().parent.parent / 'templates',
            Path(__file__).resolve().parent / 'templates',
        ],
        'OPTIONS': {
            'loaders': _template_loaders,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.dashboard.context_processors.global_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'ems_core.wsgi.application'


# ==========================================================================
# Database — Supabase PostgreSQL (primary) / SQLite (local dev fallback)
# ==========================================================================

import re
import urllib.parse

db_url = get_env_str('DATABASE_URL') or get_env_str('SUPABASE_DB_URL')
db_password = get_env_str('DB_PASSWORD') or get_env_str('SUPABASE_PASSWORD') or get_env_str('PGPASSWORD')
db_host = get_env_str('DB_HOST') or get_env_str('SUPABASE_HOST') or get_env_str('PGHOST')
db_user = get_env_str('DB_USER') or get_env_str('SUPABASE_USER') or get_env_str('PGUSER') or 'postgres'
db_name = get_env_str('DB_NAME') or get_env_str('SUPABASE_DB') or get_env_str('PGDATABASE') or 'postgres'
db_port = get_env_int('DB_PORT', get_env_int('PGPORT', 5432))

# Auto-construct db_url from components if provided
if not db_url and db_password and db_host:
    encoded_pass = urllib.parse.quote_plus(db_password)
    db_url = f"postgresql://{db_user}:{encoded_pass}@{db_host}:{db_port}/{db_name}?sslmode=require"

# Smart Database URL Sanitizer & Pooler Adapter:
# 1. Handles passwords with unencoded '@' symbols (e.g., user:pass@word@host:port/db)
# 2. Converts direct IPv6 Supabase URLs to IPv4 Pooler URLs for AWS Lambda/Vercel compatibility
# 3. Pure standard library - zero external dependency requirement
DATABASES = None

if db_url:
    try:
        url_clean = db_url.strip()
        if '://' in url_clean:
            prefix, rest = url_clean.split('://', 1)
        else:
            rest = url_clean

        # Split credentials from host/path
        auth_part, host_path = rest.rsplit('@', 1)
        if ':' in auth_part:
            u_user, u_pwd = auth_part.split(':', 1)
        else:
            u_user, u_pwd = auth_part, ''

        # Split host:port from path/database
        if '/' in host_path:
            host_port, path_query = host_path.split('/', 1)
        else:
            host_port, path_query = host_path, 'postgres'

        if ':' in host_port:
            u_host, u_port_str = host_port.split(':', 1)
            u_port = int(u_port_str)
        else:
            u_host = host_port
            u_port = 5432

        # Convert Supabase direct host to IPv4 Transaction Pooler (Port 6543)
        if 'supabase.co' in u_host and 'pooler.supabase.com' not in u_host:
            proj_match = re.search(r'db\.([a-z0-9]+)\.supabase\.co', u_host)
            if proj_match:
                proj_ref = proj_match.group(1)
                u_host = 'aws-0-ap-south-1.pooler.supabase.com'
                u_port = 6543
                if not u_user.startswith('postgres.'):
                    u_user = f"postgres.{proj_ref}"

        raw_pwd = urllib.parse.unquote_plus(u_pwd)
        clean_db = (path_query.split('?')[0] if path_query else 'postgres').strip() or 'postgres'

        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': clean_db,
                'USER': u_user,
                'PASSWORD': raw_pwd,
                'HOST': u_host,
                'PORT': u_port,
                'OPTIONS': {
                    'sslmode': 'require',
                    'connect_timeout': 5,
                    'keepalives': 1,
                    'keepalives_idle': 30,
                    'keepalives_interval': 10,
                    'keepalives_count': 5,
                },
                'CONN_MAX_AGE': get_env_int('CONN_MAX_AGE', 300),
                'CONN_HEALTH_CHECKS': False,
            }
        }
    except Exception as e:
        print(f"Database parsing error: {e}")
        DATABASES = None

if not db_url:
    DB_PATH = BASE_DIR / 'db.sqlite3'

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': DB_PATH,
        }
    }

if DATABASES is None:
    DB_PATH = BASE_DIR / 'db.sqlite3'
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': DB_PATH,
        }
    }


# ==========================================================================
# In-Memory Cache (Ultra-Fast RAM Caching for Database Aggregations)
# ==========================================================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'ems-cache',
        'TIMEOUT': 60,
    }
}


# ==========================================================================
# Authentication
# ==========================================================================


AUTHENTICATION_BACKENDS = [
    'apps.dashboard.auth_backend.ServerlessAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]


# ==========================================================================
# Internationalization
# ==========================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True


# ==========================================================================
# Static & Media Files
# ==========================================================================

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG  # Only auto-refresh in development

# Determine whitenoise availability cleanly
_has_whitenoise = False
try:
    import whitenoise
    _has_whitenoise = True
except ImportError:
    pass

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage" if _has_whitenoise else "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
if os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or (os.path.exists('/tmp') and not os.access(str(BASE_DIR), os.W_OK)):
    MEDIA_ROOT = Path('/tmp/media')
    try:
        os.makedirs('/tmp/media', exist_ok=True)
    except Exception:
        pass
else:
    MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ==========================================================================
# REST Framework
# ==========================================================================

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}


# ==========================================================================
# Email Configuration (Gmail SMTP) — credentials from .env only
# ==========================================================================

EMAIL_HOST_USER = get_env_str('EMAIL_HOST_USER', '').strip()
EMAIL_HOST_PASSWORD = get_env_str('EMAIL_HOST_PASSWORD', '').strip().replace(' ', '')
_default_email_backend = 'django.core.mail.backends.smtp.EmailBackend' if (EMAIL_HOST_USER and EMAIL_HOST_PASSWORD) else 'django.core.mail.backends.console.EmailBackend'
EMAIL_BACKEND = get_env_str('EMAIL_BACKEND', _default_email_backend)
EMAIL_HOST = get_env_str('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = get_env_int('EMAIL_PORT', 587)
EMAIL_USE_TLS = get_env_bool('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = get_env_bool('EMAIL_USE_SSL', False)
EMAIL_TIMEOUT = get_env_int('EMAIL_TIMEOUT', 8)
DEFAULT_FROM_EMAIL = get_env_str('DEFAULT_FROM_EMAIL', f'Nizhal Community <{EMAIL_HOST_USER}>' if EMAIL_HOST_USER else 'noreply@example.com')
SERVER_EMAIL = DEFAULT_FROM_EMAIL



# ==========================================================================
# Security — CSRF, Cookies, HTTPS
# ==========================================================================

CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://127.0.0.1:8001',
    'http://localhost:8001',
    'https://*.vercel.app',
    'https://admin-nizhal-community.vercel.app',
    'https://admin.nizhalcommunity.in',
    'https://www.admin.nizhalcommunity.in',
    'https://nizhalcommunity.in',
    'https://www.nizhalcommunity.in',
    'https://*.nizhalcommunity.in',
]
X_FRAME_OPTIONS = 'SAMEORIGIN'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# Authentication & Stateless Session Security (works across serverless lambda instances)
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard-overview'
LOGOUT_REDIRECT_URL = 'login'

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_NAME = 'ems_sessionid'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 1209600  # 14 days persistent session
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = not DEBUG
CSRF_FAILURE_VIEW = 'apps.dashboard.auth_views.csrf_failure_view'

# Production HTTPS security headers
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
