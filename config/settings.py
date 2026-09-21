"""
Django settings for the "Location Popularity Map" test task.

Everything environment-specific is read from env vars (see .env.example),
so the same settings module works locally (sqlite fallback), in tests, and
in Docker Compose (Postgres + Redis).
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Loads .env into os.environ for local (non-Docker) runs. Docker Compose
# already injects vars via `env_file`, so this is a no-op there — but a
# harmless one, and it's what makes `pip install -r requirements.txt` +
# `.env` "just work" without Docker too.
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
DEBUG = os.environ.get("DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]

TESTING = "test" in sys.argv or "pytest" in sys.modules

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "apps.accounts",
    "apps.locations",
    "apps.reviews",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
USE_SQLITE = os.environ.get("USE_SQLITE", "0") == "1" or TESTING

if USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / ("test_db.sqlite3" if TESTING else "db.sqlite3"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "location_map"),
            "USER": os.environ.get("DB_USER", "location_map"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "location_map"),
            "HOST": os.environ.get("DB_HOST", "db"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }

# ---------------------------------------------------------------------------
# Cache / Redis
# ---------------------------------------------------------------------------
REDIS_URL = os.environ.get("REDIS_URL", "")

if REDIS_URL and not TESTING:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }
else:
    # Local dev / tests: no real Redis needed. Rate-limiting and cache
    # invalidation code paths are identical — only the backend differs.
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "location-popularity-map",
        }
    }

CACHE_TTL_LOCATIONS_LIST = int(os.environ.get("CACHE_TTL_LOCATIONS_LIST", 60 * 5))
VIEW_RATE_LIMIT_SECONDS = int(os.environ.get("VIEW_RATE_LIMIT_SECONDS", 60 * 60))

# ---------------------------------------------------------------------------
# Auth / passwords
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# I18N
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "uk"
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    # Disable DRF's ?format= content-negotiation override so /locations/export/
    # can use ?format=json|csv as its own export type (otherwise ?format=csv → 404).
    "URL_FORMAT_OVERRIDE": None,
}

# SessionAuthentication requires CSRF for unsafe methods by default, which is
# correct for a cookie-based browser client. Frontend must send the
# X-CSRFToken header (read from the csrftoken cookie) on POST/PUT/PATCH/DELETE.
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_HTTPONLY = True
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# In local dev over plain HTTP, secure cookies would block the browser from
# storing them at all — keep this in sync with how the API is actually served.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

CORS_ALLOW_CREDENTIALS = True

AUTH_USER_MODEL = "auth.User"

LOGIN_URL = "/api/auth/login/"

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@location-map.local")
EMAIL_HOST = os.environ.get("SMTP_HOST", "")
EMAIL_PORT = int(os.environ.get("SMTP_PORT", 587))
EMAIL_HOST_USER = os.environ.get("SMTP_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("SMTP_USE_TLS", "1") == "1"

FRONTEND_PASSWORD_RESET_URL = os.environ.get(
    "FRONTEND_PASSWORD_RESET_URL", "http://localhost:3000/reset-password"
)

# ---------------------------------------------------------------------------
# Popularity formula weights (see apps/locations/services.py)
# ---------------------------------------------------------------------------
POPULARITY_RATING_WEIGHT = float(os.environ.get("POPULARITY_RATING_WEIGHT", 2.0))
POPULARITY_REVIEWS_WEIGHT = float(os.environ.get("POPULARITY_REVIEWS_WEIGHT", 1.5))
POPULARITY_VIEWS_WEIGHT = float(os.environ.get("POPULARITY_VIEWS_WEIGHT", 0.5))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
