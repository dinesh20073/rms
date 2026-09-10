import os
import shutil
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

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

SECRET_KEY = get_env_str('DJANGO_SECRET_KEY', 'django-insecure-ems-super-secret-key-2026-v1-production-ready')
DEBUG = get_env_bool('DJANGO_DEBUG', True)

ALLOWED_HOSTS = ['*']

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

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.dashboard.middleware.BankSessionSecurityMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ems_core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
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

# Database
# Clean environment-based database configuration (reads from DATABASE_URL or Supabase env vars)
db_url = get_env_str('DATABASE_URL') or get_env_str('SUPABASE_DB_URL')
db_password = get_env_str('DB_PASSWORD') or get_env_str('SUPABASE_PASSWORD') or get_env_str('PGPASSWORD')
db_host = get_env_str('DB_HOST') or get_env_str('SUPABASE_HOST') or get_env_str('PGHOST')
db_user = get_env_str('DB_USER') or get_env_str('SUPABASE_USER') or get_env_str('PGUSER') or 'postgres'
db_name = get_env_str('DB_NAME') or get_env_str('SUPABASE_DB') or get_env_str('PGDATABASE') or 'postgres'
db_port = get_env_int('DB_PORT', get_env_int('PGPORT', 5432))

if not db_url and db_password and db_host:
    import urllib.parse
    encoded_pass = urllib.parse.quote_plus(db_password)
    db_url = f"postgresql://{db_user}:{encoded_pass}@{db_host}:{db_port}/{db_name}?sslmode=require"

if db_url:
    try:
        import dj_database_url
        DATABASES = {
            'default': dj_database_url.config(
                default=db_url,
                conn_max_age=0,
                ssl_require=True
            )
        }
    except Exception:
        db_url = None



if not db_url:
    if 'VERCEL' in os.environ or os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
        tmp_db = Path('/tmp/db.sqlite3')
        orig_db = BASE_DIR / 'db.sqlite3'
        if orig_db.exists() and not tmp_db.exists():
            try:
                shutil.copyfile(orig_db, tmp_db)
            except Exception:
                pass
        DB_PATH = tmp_db
    else:
        DB_PATH = BASE_DIR / 'db.sqlite3'

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': DB_PATH,
        }
    }

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

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

# Email Configuration (Gmail SMTP)
EMAIL_BACKEND = get_env_str('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = get_env_str('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = get_env_int('EMAIL_PORT', 587)
EMAIL_USE_TLS = get_env_bool('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = get_env_str('EMAIL_HOST_USER', 'nizhalcommunity@gmail.com')
EMAIL_HOST_PASSWORD = get_env_str('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = get_env_str('DEFAULT_FROM_EMAIL', f'Nizhal Community <{EMAIL_HOST_USER}>')

# CSRF & Frame Options
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://127.0.0.1:8001',
    'http://localhost:8001',
    'https://*.vercel.app',
    'https://admin-nizhal-community.vercel.app',
]
X_FRAME_OPTIONS = 'SAMEORIGIN'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

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
SESSION_COOKIE_SECURE = False

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_FAILURE_VIEW = 'apps.dashboard.auth_views.csrf_failure_view'

