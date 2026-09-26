"""
Django settings for food_delivery project.
Nutrient – The Super Food (Single Restaurant Food Delivery Platform)
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'insecure-dev-key-change-in-production-nutrient')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't', 'yes')

ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if h.strip()]

# Auto-detect Cloud PaaS hostnames (Railway, Render)
railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN')
if railway_domain and railway_domain not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(railway_domain)
if os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_SERVICE_NAME'):
    for host in ('.railway.app', '.up.railway.app'):
        if host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)

render_hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME')
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)
if os.getenv('RENDER') and '.onrender.com' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.onrender.com')

# CSRF Trusted Origins (required for cloud PaaS deployments like Render, Railway, Heroku)
csrf_origins_env = os.getenv('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins_env.split(',') if o.strip()]
if not CSRF_TRUSTED_ORIGINS:
    for host in ALLOWED_HOSTS:
        if host not in ('*', '127.0.0.1', 'localhost'):
            if host.startswith('.'):
                CSRF_TRUSTED_ORIGINS.append(f'https://*{host}')
            else:
                CSRF_TRUSTED_ORIGINS.append(f'https://{host}')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Nutrient Apps (Single Restaurant Architecture)
    'accounts.apps.AccountsConfig',
    'restaurant.apps.RestaurantConfig',
    'menu.apps.MenuConfig',
    'cart.apps.CartConfig',
    'orders.apps.OrdersConfig',
    'delivery.apps.DeliveryConfig',
    'payments.apps.PaymentsConfig',
    'reviews.apps.ReviewsConfig',
    'subscriptions.apps.SubscriptionsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'food_delivery.urls'

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
                'restaurant.context_processors.restaurant_info',
                'cart.context_processors.cart_status',
            ],
        },
    },
]

WSGI_APPLICATION = 'food_delivery.wsgi.application'

# Database Configuration
# Cloud PaaS: DATABASE_URL, MYSQL_URL, POSTGRES_URL (via dj-database-url)
# Railway Native MySQL: MYSQLHOST, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE, MYSQLPORT
# Local Primary: MySQL (macOS Homebrew / Community Server via PyMySQL wrapper)
# Cloud Fallback: SQLite if in PaaS container without remote DB linked, or if USE_SQLITE=True
DATABASE_URL = (
    os.getenv('DATABASE_URL')
    or os.getenv('MYSQL_URL')
    or os.getenv('POSTGRES_URL')
    or os.getenv('POSTGRESQL_URL')
)
DB_ENGINE = os.getenv('DB_ENGINE', 'django.db.backends.mysql')
USE_SQLITE = os.getenv('USE_SQLITE', 'False').lower() in ('true', '1', 't', 'yes')

is_cloud_platform = bool(
    os.getenv('RAILWAY_ENVIRONMENT')
    or os.getenv('RAILWAY_SERVICE_NAME')
    or os.getenv('RENDER')
    or os.getenv('DYNO')
)
mysql_host = os.getenv('MYSQLHOST') or (
    os.getenv('DB_HOST') if not is_cloud_platform or os.getenv('DB_HOST') != '127.0.0.1' else None
)

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
elif mysql_host and mysql_host != '127.0.0.1':
    # Remote/managed MySQL (e.g. Railway MySQL with individual variables)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DB_NAME') or os.getenv('MYSQLDATABASE') or 'nutrient_db',
            'USER': os.getenv('DB_USER') or os.getenv('MYSQLUSER') or 'root',
            'PASSWORD': os.getenv('DB_PASSWORD') or os.getenv('MYSQLPASSWORD') or '',
            'HOST': mysql_host,
            'PORT': os.getenv('DB_PORT') or os.getenv('MYSQLPORT') or '3306',
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'; SET NAMES 'utf8mb4' COLLATE 'utf8mb4_unicode_ci';",
            },
        }
    }
elif USE_SQLITE or DB_ENGINE == 'django.db.backends.sqlite3' or (is_cloud_platform and (not mysql_host or mysql_host == '127.0.0.1')):
    # Safe fallback to SQLite in cloud container when no external DB is attached yet
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    # Local developer default: MySQL on 127.0.0.1:3306
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DB_NAME', 'nutrient_db'),
            'USER': os.getenv('DB_USER', 'root'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', '127.0.0.1'),
            'PORT': os.getenv('DB_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'; SET NAMES 'utf8mb4' COLLATE 'utf8mb4_unicode_ci';",
            },
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise production static file compression and caching
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Media files (Food photos, banners, receipts)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Nutrient Brand Metadata
RESTAURANT_NAME = os.getenv('RESTAURANT_NAME', 'Nutrient – The Super Food')
RESTAURANT_TAGLINE = os.getenv('RESTAURANT_TAGLINE', 'Eat Clean. Stay Strong. Live Better.')
RESTAURANT_PHONE = os.getenv('RESTAURANT_PHONE', '+91 7993476624')
RESTAURANT_LOCATION = os.getenv('RESTAURANT_LOCATION', 'Hyderabad, Telangana, India')
CURRENCY_SYMBOL = '₹'

# Production Security Hardening (Activated automatically when DEBUG=False)
if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 'yes')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
