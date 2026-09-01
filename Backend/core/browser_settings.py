from .test_settings import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
DATABASES["default"]["NAME"] = str(BASE_DIR / "browser.sqlite3")  # noqa: F405
RATELIMIT_ENABLE = False
