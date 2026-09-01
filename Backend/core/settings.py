import json
from pathlib import Path

from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
APP_ENV = config("APP_ENV", default="development")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())
PUBLIC_BASE_URL = config("PUBLIC_BASE_URL").rstrip("/")
PUBLIC_CONSOLE_URL = config("PUBLIC_CONSOLE_URL", default="http://localhost:4200").rstrip("/")
CASHFREE_DIGILOCKER_REDIRECT_URL = config("CASHFREE_DIGILOCKER_REDIRECT_URL", default="").strip()
TIME_ZONE = config("TIME_ZONE", default="Asia/Kolkata")
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", cast=Csv())
ADMIN_URL = config("ADMIN_URL", default="admin/").strip("/") + "/"
FIELD_ENCRYPTION_KEY = config("FIELD_ENCRYPTION_KEY", default="")
SENTRY_DSN = config("SENTRY_DSN", default="")
LEGAL_ENTITY_NAME = config("LEGAL_ENTITY_NAME", default="PAYSWAP FINTECH PRIVATE LIMITED")
GRIEVANCE_OFFICER_NAME = config("GRIEVANCE_OFFICER_NAME", default="ABHISHEK BANSAL")
GRIEVANCE_EMAIL = config("GRIEVANCE_EMAIL", default="Abhishek@payswap.in")
GRIEVANCE_POSTAL_ADDRESS = config(
    "GRIEVANCE_POSTAL_ADDRESS",
    default="4TH, C-24 A, PANKAJ SINGHVI MARG, LAL KOTHI, Jaipur, Rajasthan, 302015, India",
)

# Company tax identifiers printed on generated purchase orders (A4 documents).
# Empty values render as "As registered" in development; set real values in
# staging/production so the documents are compliance-complete.
COMPANY_GSTIN = config("COMPANY_GSTIN", default="")
COMPANY_PAN = config("COMPANY_PAN", default="")
COMPANY_VOUCHER_HSN = config("COMPANY_VOUCHER_HSN", default="4907")

PRODUCTION_ENVS = frozenset({"staging", "production"})
IS_PRODUCTION = APP_ENV in PRODUCTION_ENVS
ADMIN_ALLOWED_IPS = config("ADMIN_ALLOWED_IPS", default="", cast=Csv())
# The admin IP allowlist is optional in every environment. Empty means no IP
# restriction; set CIDRs to restrict Django admin to office/VPN networks.
# X-Forwarded-For is attacker-spoofable unless a trusted proxy strips/overwrites
# it. Off by default everywhere; enable explicitly in deployments behind a known
# load balancer.
ADMIN_TRUST_X_FORWARDED_FOR = config("ADMIN_TRUST_X_FORWARDED_FOR", default=False, cast=bool)
# Authenticator (TOTP) policy: optional for all users in development. In
# staging/production it is mandatory for platform admins (portal admins are
# forced to enrol at login and Django admin requires a verified OTP device) and
# stays optional for every other user.
ADMIN_REQUIRE_OTP = config("ADMIN_REQUIRE_OTP", default=IS_PRODUCTION, cast=bool)
# TOTP enrolment for employees holding these role slugs (all environments).
STAFF_REQUIRE_OTP_ROLES = config("STAFF_REQUIRE_OTP_ROLES", default="operations,kyc", cast=Csv())
SESSION_COOKIE_AGE = config("SESSION_COOKIE_AGE", default=28800, cast=int)
SESSION_IDLE_TIMEOUT_SECONDS = config("SESSION_IDLE_TIMEOUT_SECONDS", default=1800, cast=int)

if IS_PRODUCTION:
    if DEBUG:
        raise ImproperlyConfigured("DEBUG must be False when APP_ENV is staging or production.")
    if len(SECRET_KEY) < 50:
        raise ImproperlyConfigured("SECRET_KEY must be at least 50 characters.")
    if "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured("ALLOWED_HOSTS must not contain '*' in production.")
    if not FIELD_ENCRYPTION_KEY:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is required in production.")
    if not all((GRIEVANCE_OFFICER_NAME, GRIEVANCE_EMAIL, GRIEVANCE_POSTAL_ADDRESS)):
        raise ImproperlyConfigured(
            "Grievance officer name, email, and postal address are required in staging and production."
        )

INSTALLED_APPS = [
    "unfold.apps.BasicAppConfig",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "core.apps.PayswapAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "accounts",
    "access",
    "audit",
    "notifications",
    "merchants",
    "verification",
    "agreements",
    "catalog",
    "orders",
    "portals",
    "api",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "core.middleware.AdminAccessMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.RequestIDMiddleware",
    "core.middleware.RevokedSessionMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "core.middleware.IdleTimeoutMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"
WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.csp",
                "portals.context_processors.portal",
            ],
        },
    },
]

_db_engine = config("DB_ENGINE")
_db_conn_max_age = config("DB_CONN_MAX_AGE", default=60 if IS_PRODUCTION else 0, cast=int)
DATABASES = {
    "default": {
        "ENGINE": _db_engine,
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT"),
        # Persistent connections in dev exhaust local Postgres (runserver reload +
        # DigiLocker polling). Override with DB_CONN_MAX_AGE if needed.
        "CONN_MAX_AGE": _db_conn_max_age,
        "CONN_HEALTH_CHECKS": _db_conn_max_age > 0,
        # connect_timeout is libpq-only; SQLite rejects unknown options.
        "OPTIONS": {"connect_timeout": 10} if "postgresql" in _db_engine else {},
    }
}

if DEBUG and "postgresql" in _db_engine:
    MIDDLEWARE = [*MIDDLEWARE, "core.middleware.CloseDatabaseConnectionsMiddleware"]

REDIS_URL = config("REDIS_URL")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "payswaphub",
        "TIMEOUT": 300,
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = IS_PRODUCTION
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = IS_PRODUCTION

SECURE_SSL_REDIRECT = IS_PRODUCTION
SECURE_HSTS_SECONDS = 31536000 if IS_PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = IS_PRODUCTION
SECURE_HSTS_PRELOAD = IS_PRODUCTION
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if IS_PRODUCTION else None

SECURE_CSP = {
    "default-src": [CSP.NONE],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF],
    "style-src-attr": [CSP.UNSAFE_INLINE],
    "img-src": [CSP.SELF, "data:"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "form-action": [CSP.SELF],
    "base-uri": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "object-src": [CSP.NONE],
}

CELERY_BROKER_URL = config("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# Local runserver has no worker. Deliver in-process unless Redis/Celery is running
# in staging/production (override with CELERY_TASK_ALWAYS_EAGER).
CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=not IS_PRODUCTION, cast=bool)
CELERY_TASK_EAGER_PROPAGATES = CELERY_TASK_ALWAYS_EAGER

EMAIL_BACKEND = config("EMAIL_BACKEND")
EMAIL_HOST = config("EMAIL_HOST")
EMAIL_PORT = config("EMAIL_PORT", cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL")
OTP_FROM_EMAIL = config("OTP_FROM_EMAIL", default="Payswap <support@payswap.in>")
OTP_REPLY_TO_EMAIL = config("OTP_REPLY_TO_EMAIL", default="support@payswap.in")
AWS_SES_REGION = config("AWS_SES_REGION", default="ap-south-1")
AWS_SES_ACCESS_KEY_ID = config("AWS_SES_ACCESS_KEY_ID", default="")
AWS_SES_SECRET_ACCESS_KEY = config("AWS_SES_SECRET_ACCESS_KEY", default="")
KALEYRA_SID = config("KALEYRA_SID", default="") or config("KALEYRA_ACCOUNT_SID", default="")
KALEYRA_API_KEY = config("KALEYRA_API_KEY", default="")
KALEYRA_API_KEY_NAME = config("KALEYRA_API_KEY_NAME", default="")
KALEYRA_SENDER = config("KALEYRA_SENDER", default="") or config("KALEYRA_SENDER_ID", default="PYSWAP")
KALEYRA_BASE_URL = config("KALEYRA_BASE_URL", default="https://api.in.kaleyra.io")
KALEYRA_ENTITY_ID = config("KALEYRA_ENTITY_ID", default="")
KALEYRA_WEBHOOK_SECRET = config("KALEYRA_WEBHOOK_SECRET", default="")


def _json_object(raw: str) -> dict:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


KALEYRA_DLT_TEMPLATES = _json_object(config("KALEYRA_DLT_TEMPLATES", default="{}"))
CASHFREE_CLIENT_ID = config("CASHFREE_CLIENT_ID", default="")
CASHFREE_CLIENT_SECRET = config("CASHFREE_CLIENT_SECRET", default="")
CASHFREE_ENV = config("CASHFREE_ENV", default="sandbox")
CASHFREE_PUBLIC_KEY_PATH = config(
    "CASHFREE_PUBLIC_KEY_PATH",
    default=str(BASE_DIR / "Cashfree key" / "accountId_59940_public_key.pem"),
)
if not Path(CASHFREE_PUBLIC_KEY_PATH).is_absolute():
    CASHFREE_PUBLIC_KEY_PATH = str(BASE_DIR / CASHFREE_PUBLIC_KEY_PATH)
# Separate credential for inbound webhooks (x-webhook-signature HMAC). Empty =
# receiver refuses all events (fail closed).
CASHFREE_WEBHOOK_SECRET = config("CASHFREE_WEBHOOK_SECRET", default="")

# Verification reuse window (§6). A successful provider verification is reused
# while now < completed_at + VERIFICATION_CACHE_DAYS.
VERIFICATION_CACHE_DAYS = config("VERIFICATION_CACHE_DAYS", default=30, cast=int)

# Testing-only OTP bypass (§21). Accepted ONLY in development/test environments;
# enabling it in staging/production is a startup failure, and the check lives in
# the OTP service as well so a misconfigured runtime cannot silently allow it.
AUTH_TEST_MODE = config("AUTH_TEST_MODE", default=not IS_PRODUCTION, cast=bool)
TEST_OTP = config("TEST_OTP", default="123456")

OTP_EXPIRY_SECONDS = config("OTP_EXPIRY_SECONDS", default=300, cast=int)
OTP_MAX_ATTEMPTS = config("OTP_MAX_ATTEMPTS", default=5, cast=int)
OTP_RESEND_COOLDOWN_SECONDS = config("OTP_RESEND_COOLDOWN_SECONDS", default=30, cast=int)

FEATURE_DIGILOCKER = config("FEATURE_DIGILOCKER", default=True, cast=bool)
FEATURE_ESIGN = config("FEATURE_ESIGN", default=True, cast=bool)

if IS_PRODUCTION:
    if CASHFREE_ENV not in {"sandbox", "production"}:
        raise ImproperlyConfigured("CASHFREE_ENV must be 'sandbox' or 'production'.")
    if CASHFREE_ENV == "production" and not (CASHFREE_CLIENT_ID and CASHFREE_CLIENT_SECRET):
        raise ImproperlyConfigured(
            "CASHFREE_CLIENT_ID and CASHFREE_CLIENT_SECRET are required when CASHFREE_ENV=production."
        )
    if CASHFREE_ENV == "production" and not CASHFREE_WEBHOOK_SECRET:
        raise ImproperlyConfigured("CASHFREE_WEBHOOK_SECRET is required in production.")
    if AUTH_TEST_MODE:
        raise ImproperlyConfigured(
            "AUTH_TEST_MODE must be false when APP_ENV is staging or production — "
            "the test OTP must never be accepted in a live environment."
        )
CSRF_FAILURE_VIEW = "portals.views.errors.csrf_failure"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "accounts.password_policy.PayswapPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if STATIC_ROOT.resolve() == MEDIA_ROOT.resolve():
    raise ImproperlyConfigured("STATIC_ROOT and MEDIA_ROOT must be different directories.")

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": MEDIA_ROOT,
            "base_url": MEDIA_URL,
        },
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if IS_PRODUCTION
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="ap-south-1")

if AWS_STORAGE_BUCKET_NAME:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "region_name": AWS_S3_REGION_NAME,
            "default_acl": "private",
            "querystring_auth": True,
            "file_overwrite": False,
        },
    }
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 20

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/login/"
RATELIMIT_ENABLE = True
RATELIMIT_VIEW = "portals.views.errors.too_many_requests"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_context": {
            "()": "core.logging.RequestContextFilter",
        },
    },
    "formatters": {
        "console": {
            "format": "{levelname} {asctime} {name} {request_id} {message}",
            "style": "{",
        },
        "json": {
            "()": "core.logging.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if IS_PRODUCTION else "console",
            "filters": ["request_context"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.security": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "payswap.notifications": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

UNFOLD = {
    "SITE_TITLE": "Payswap admin",
    "SITE_HEADER": "Payswap",
    "SITE_SUBHEADER": "Power of Banking",
    "SITE_URL": "/administration/",
    "SITE_SYMBOL": "account_balance",
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "href": lambda request: "/static/images/logo/favicon-icon.png",
        }
    ],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "ENVIRONMENT": "core.admin_ui.environment_callback",
    "LOGIN": {
        "form": "core.admin.PayswapAdminAuthenticationForm",
    },
    "COLORS": {
        "primary": {
            "50": "oklch(96% 0.03 250)",
            "100": "oklch(92% 0.05 250)",
            "200": "oklch(86% 0.08 250)",
            "300": "oklch(76% 0.12 250)",
            "400": "oklch(66% 0.14 245)",
            "500": "oklch(52% 0.14 255)",
            "600": "oklch(45% 0.13 255)",
            "700": "oklch(38% 0.11 255)",
            "800": "oklch(32% 0.09 255)",
            "900": "oklch(26% 0.07 255)",
            "950": "oklch(18% 0.05 255)",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "Operations",
                "separator": True,
                "items": [
                    {
                        "title": "Administration portal",
                        "icon": "dashboard",
                        "link": "/administration/",
                    },
                ],
            },
        ],
    },
}

if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=APP_ENV,
        send_default_pii=False,
        traces_sample_rate=0.0,
    )
