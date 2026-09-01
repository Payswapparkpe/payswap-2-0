"""Capture role/flow screenshots for the documentation guide."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = Path("docs/guides/screenshots")
PASSWORD = "CorrectHorse9!"
User = get_user_model()

SHOTS = [
    ("01-login", None, "/login/"),
    ("02-merchant-register", None, "/merchant/register/"),
    ("10-merchant-dashboard", "merchant@payswap.local", "/merchant/"),
    ("11-merchant-onboarding", "merchant@payswap.local", "/merchant/onboarding/"),
    ("12-merchant-verification", "merchant@payswap.local", "/merchant/verification/"),
    ("13-merchant-documents", "merchant@payswap.local", "/merchant/documents/"),
    ("14-merchant-agreements", "merchant@payswap.local", "/merchant/agreements/"),
    ("15-merchant-orders", "merchant@payswap.local", "/merchant/orders/"),
    ("16-merchant-order-create", "merchant@payswap.local", "/merchant/orders/new/"),
    ("17-merchant-order-detail", "merchant@payswap.local", "/merchant/orders/ORD-000001/"),
    ("18-merchant-profile", "merchant@payswap.local", "/merchant/profile/"),
    ("20-kyc-dashboard", "kyc@payswap.local", "/employee/"),
    ("21-kyc-queue", "kyc@payswap.local", "/employee/queue/"),
    ("30-ops-dashboard", "ops@payswap.local", "/employee/"),
    ("31-ops-orders", "ops@payswap.local", "/employee/orders/"),
    ("32-ops-order-detail", "ops@payswap.local", "/employee/orders/ORD-000001/"),
    ("40-admin-dashboard", "admin@payswap.local", "/administration/"),
    ("41-admin-merchants", "admin@payswap.local", "/administration/merchants/"),
    ("42-admin-onboarding", "admin@payswap.local", "/administration/onboarding/"),
    ("43-admin-verification", "admin@payswap.local", "/administration/verification/"),
    ("44-admin-orders", "admin@payswap.local", "/administration/orders/"),
    ("45-admin-audit", "admin@payswap.local", "/administration/audit/"),
    ("46-admin-roles", "admin@payswap.local", "/administration/roles/"),
    ("47-admin-security", "admin@payswap.local", "/administration/security/"),
]


def session_cookie_for(email: str) -> dict:
    user = User.objects.get(email=email)
    store = SessionStore()
    store["_auth_user_id"] = str(user.pk)
    store["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    store["_auth_user_hash"] = user.get_session_auth_hash()
    # Skip MFA challenge for documentation capture.
    store["otp_device_id"] = "docs-bypass"
    store.save()
    return {
        "name": settings.SESSION_COOKIE_NAME,
        "value": store.session_key,
        "domain": "127.0.0.1",
        "path": "/",
        "httpOnly": True,
        "secure": False,
        "sameSite": "Lax",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cookies = {
        email: session_cookie_for(email)
        for email in {email for _n, email, _p in SHOTS if email}
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        current_email = object()
        context = None
        page = None
        for name, email, path in SHOTS:
            if email != current_email:
                if context is not None:
                    context.close()
                context = browser.new_context(viewport={"width": 1440, "height": 900})
                if email:
                    context.add_cookies([cookies[email]])
                page = context.new_page()
                current_email = email
            assert page is not None
            page.goto(f"{BASE}{path}", wait_until="networkidle")
            page.wait_for_timeout(350)
            target = OUT / f"{name}.png"
            page.screenshot(path=str(target), full_page=True)
            print("saved", target)
        if context is not None:
            context.close()
        browser.close()


if __name__ == "__main__":
    main()
