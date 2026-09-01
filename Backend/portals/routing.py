from urllib.parse import urlparse

from django.conf import settings

from accounts.models import User

LOGIN_PATH = "/login/"
LOGOUT_PATH = "/logout/"
MFA_PATH = "/mfa/"
MFA_SETUP_PATH = "/mfa/setup/"


def merchant_console_url(path: str = "/app") -> str:
    """Angular partner console URL when configured; else legacy Django merchant portal."""
    base = getattr(settings, "PUBLIC_CONSOLE_URL", "").rstrip("/")
    if not base:
        return "/merchant/"
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def partner_login_url() -> str:
    return merchant_console_url("/login")


_HOMES = {
    User.UserType.ADMIN: "/administration/",
    User.UserType.EMPLOYEE: "/employee/",
}


def portal_home(user) -> str:
    if user is None or not getattr(user, "is_authenticated", False):
        return LOGIN_PATH
    user_type = getattr(user, "user_type", "")
    if user_type == User.UserType.MERCHANT:
        return merchant_console_url("/app")
    return _HOMES.get(user_type, LOGIN_PATH)


def is_safe_next(next_url: str, user) -> bool:
    if not next_url or not isinstance(next_url, str):
        return False
    candidate = next_url.strip()
    if candidate.startswith("http://") or candidate.startswith("https://"):
        console_base = getattr(settings, "PUBLIC_CONSOLE_URL", "").rstrip("/")
        if console_base and candidate.startswith(console_base):
            return getattr(user, "user_type", "") == User.UserType.MERCHANT
        return False
    if not candidate.startswith("/") or candidate.startswith("//") or "\\" in candidate:
        return False
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return False
    path = parsed.path or "/"
    user_type = getattr(user, "user_type", "")
    if user_type == User.UserType.MERCHANT:
        return path == "/merchant/" or path.startswith("/merchant/")
    home = _HOMES.get(user_type, "").rstrip("/")
    if not home or home.startswith("http"):
        return False
    return path == home or path == f"{home}/" or path.startswith(f"{home}/")


def post_login_url(request, user) -> str:
    nxt = ""
    if request is not None:
        nxt = request.POST.get("next") or request.GET.get("next") or ""
        session = getattr(request, "session", None)
        if not nxt and session is not None:
            nxt = session.pop("post_login_next", "") or ""
    if is_safe_next(nxt, user):
        return nxt
    return portal_home(user)
