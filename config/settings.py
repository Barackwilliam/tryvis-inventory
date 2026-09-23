"""
Tryvis Inventory Management System - settings.

This is a project of its own, deployed as its own Render service, but it talks
to the SAME Supabase Postgres that serves www.tryvis.co.tz. The two are kept
apart by a dedicated Postgres schema (DB_SCHEMA, default "inventory"), so this
project gets its own django_migrations, its own auth_user and its own tables
without ever touching the website's.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path=BASE_DIR / ".env"):
    """
    Read .env into os.environ without any third-party package.

    Real environment variables always win, so Render's dashboard values are
    never overwritten by a stray .env that got committed by accident.
    """
    if not path.exists():
        return

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[7:].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_env_file()


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [part.strip() for part in os.environ.get(name, default).split(",") if part.strip()]


# --- core ----------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "catalog",
    "inventory",
    "purchasing",
    "sales",
    "jobs",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.inventory_context",
            ],
        },
    },
]

# --- database ------------------------------------------------------------
# Same Supabase instance as the website, different schema.
DB_SCHEMA = os.environ.get("DB_SCHEMA", "inventory")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "postgres"),
        "USER": os.environ.get("DB_USER", ""),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", ""),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", 0)),
        "OPTIONS": {
            # ONLY this project's schema - deliberately no "public" fallback.
            #
            # With "inventory,public" Postgres silently falls back to public for
            # any table it cannot find in inventory. Django would then read the
            # website's django_migrations and auth_user as if they were its own.
            # Built-in types still resolve through pg_catalog, so nothing is lost.
            "options": f"-c search_path={DB_SCHEMA}",
        },
    }
}

# Local development without Postgres
if env_bool("USE_SQLITE"):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- locale --------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "Africa/Dar_es_Salaam")
USE_I18N = True
USE_TZ = True

# --- static --------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
# BUG guarded here: the manifest backend refuses to serve any file that is not
# in staticfiles.json, so it raises "Missing staticfiles manifest entry" during
# tests and on any run where collectstatic has not happened yet. Hashed names
# belong in production; everywhere else plain files are correct.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or env_bool("SKIP_STATIC_MANIFEST")
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# --- email (low stock alerts) -------------------------------------------
if os.environ.get("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["EMAIL_HOST"]
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "inventory@tryvis.co.tz")

# --- auth flow -----------------------------------------------------------
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "inventory:dashboard"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_AGE = 60 * 60 * 10  # a working day

# --- the written briefing ------------------------------------------------
# Optional. Without a key the briefing is still written, by the system itself.
# Key: https://console.x.ai  ·  Model ids: https://docs.x.ai/docs/models
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4-1-fast")

# --- help material for the support assistant -----------------------------
# Served at /help/knowledge.txt. Leave the token blank to keep the link open;
# set it to require ?k=<token>.
HELP_DOC_TOKEN = os.environ.get("HELP_DOC_TOKEN", "")

# --- company -------------------------------------------------------------
COMPANY_NAME = os.environ.get("COMPANY_NAME", "Tryvis Investments Limited")
COMPANY_TAGLINE = os.environ.get("COMPANY_TAGLINE", "Industrial Engineering & Supply")
COMPANY_ADDRESS = os.environ.get("COMPANY_ADDRESS", "Dar es Salaam, Tanzania")
COMPANY_WEBSITE = os.environ.get("COMPANY_WEBSITE", "www.tryvis.co.tz")
COMPANY_PHONE = os.environ.get("COMPANY_PHONE", "")
COMPANY_TIN = os.environ.get("COMPANY_TIN", "")
ITEM_CODE_COMPANY_PREFIX = os.environ.get("ITEM_CODE_COMPANY_PREFIX", "TIL")
VAT_RATE_PERCENT = os.environ.get("VAT_RATE_PERCENT", "18")

# --- security when live --------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    X_FRAME_OPTIONS = "DENY"
