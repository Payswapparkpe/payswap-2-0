import uuid
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.utils import timezone

from accounts.models import UserSession
from core.ip import client_ip, ip_is_allowed, parse_ip_networks
from core.logging import set_log_context

ADMIN_CSP = (
    "default-src 'none'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "style-src-attr 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'"
)


def _admin_prefix() -> str:
    prefix = getattr(settings, "ADMIN_URL", "admin/")
    return f"/{prefix.lstrip('/')}"


def _is_admin_path(path: str) -> bool:
    prefix = _admin_prefix()
    return path == prefix.rstrip("/") or path.startswith(prefix)


class RequestIDMiddleware:
    header = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.META.get(self.header) or uuid.uuid4().hex
        user = getattr(request, "user", None)
        user_id = ""
        if user is not None and getattr(user, "is_authenticated", False):
            user_id = str(getattr(user, "pk", "") or "")
        set_log_context(
            request_id=request.request_id,
            user_id=user_id,
            ip=client_ip(request) or "",
        )
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        return response


class IdleTimeoutMiddleware:
    """Expire authenticated sessions after SESSION_IDLE_TIMEOUT_SECONDS of inactivity."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        session = getattr(request, "session", None)
        if user is not None and getattr(user, "is_authenticated", False) and session is not None:
            now = timezone.now()
            raw = session.get("idle_at")
            idle_at = None
            if raw:
                try:
                    idle_at = datetime.fromisoformat(raw)
                    if timezone.is_naive(idle_at):
                        idle_at = timezone.make_aware(idle_at, timezone.get_current_timezone())
                except (TypeError, ValueError):
                    idle_at = None
            timeout = int(getattr(settings, "SESSION_IDLE_TIMEOUT_SECONDS", 1800) or 0)
            if idle_at and timeout and (now - idle_at).total_seconds() > timeout:
                logout(request)
                messages.info(request, "Your session expired due to inactivity. Sign in again.")
                return redirect(getattr(settings, "LOGIN_URL", "/login/"))
            session["idle_at"] = now.isoformat()
            last = getattr(user, "last_activity_at", None)
            if last is None or (now - last).total_seconds() >= 60:
                user.last_activity_at = now
                user.save(update_fields=["last_activity_at"])
        return self.get_response(request)


class RevokedSessionMiddleware:
    """Reject Django sessions that operators have force-revoked."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        session = getattr(request, "session", None)
        session_key = getattr(session, "session_key", None) if session is not None else None
        if (
            user is not None
            and getattr(user, "is_authenticated", False)
            and session_key
            and UserSession.objects.filter(
                user=user, session_key=session_key, revoked_at__isnull=False
            ).exists()
        ):
            logout(request)
        return self.get_response(request)


class AdminAccessMiddleware:
    """Restrict Django admin by client IP in production and relax CSP for Unfold."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if _is_admin_path(request.path) and getattr(settings, "IS_PRODUCTION", False):
            networks = parse_ip_networks(getattr(settings, "ADMIN_ALLOWED_IPS", []))
            # The allowlist is optional: an empty list means no IP restriction.
            if networks and not ip_is_allowed(client_ip(request), networks):
                return HttpResponseForbidden("Admin access is not allowed from this network.")
        response = self.get_response(request)
        if _is_admin_path(request.path):
            response["Content-Security-Policy"] = ADMIN_CSP
        return response
