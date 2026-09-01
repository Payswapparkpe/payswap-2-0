from .settings import *  # noqa: F403

DEBUG = True
IS_PRODUCTION = False
PUBLIC_CONSOLE_URL = ""

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "payswaphub-tests",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
MEDIA_ROOT = BASE_DIR / "media_test"  # noqa: F405
from cryptography.fernet import Fernet

FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
RATELIMIT_ENABLE = False
OTP_TOTP_THROTTLE_FACTOR = 0
ADMIN_REQUIRE_OTP = False
ADMIN_ALLOWED_IPS = []
ADMIN_TRUST_X_FORWARDED_FOR = False

# Tests never collectstatic; whitenoise would only warn about the missing dir.
MIDDLEWARE = [mw for mw in MIDDLEWARE if "whitenoise" not in mw]  # noqa: F405
