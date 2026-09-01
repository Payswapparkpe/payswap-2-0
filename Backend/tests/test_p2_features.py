"""Regression tests for P2 features: lockout, password reset, webhooks,
health endpoints, notification preferences, and the postal lookup."""

import base64
import hashlib
import hmac
import json
import re

import pytest
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from accounts.models import UserSession
from accounts.services import LockoutService, SessionService
from audit.models import WebhookEvent
from merchants.models import Merchant
from merchants.services import MerchantOnboardingService
from notifications.models import NotificationPreference
from notifications.services import NotificationService
from orders.models import OrderStatus
from orders.services import PaymentOrderService
from tests.support import complete_required_draft


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _fail_login(client, email):
    return client.post("/login/", {"email": email, "password": "WrongPass!234"}, follow=False)


@pytest.mark.django_db
class TestAccountLockout:
    def test_locks_after_five_failures(self, client, merchant_user):
        for _ in range(5):
            response = _fail_login(client, merchant_user.email)
            assert response.status_code == 400
        response = _fail_login(client, merchant_user.email)
        assert response.status_code == 429
        assert b"Too many failed sign-in attempts" in response.content

    def test_locked_account_rejects_even_correct_password(self, client, merchant_user):
        for _ in range(5):
            _fail_login(client, merchant_user.email)
        response = client.post("/login/", {"email": merchant_user.email, "password": "CorrectHorse9!"})
        assert response.status_code == 429
        # The password was never evaluated: still logged out.
        assert "_auth_user_id" not in client.session

    def test_successful_login_clears_counter(self, client, merchant_user):
        for _ in range(4):
            _fail_login(client, merchant_user.email)
        response = client.post("/login/", {"email": merchant_user.email, "password": "CorrectHorse9!"})
        assert response.status_code == 302
        assert LockoutService.locked_seconds_remaining(merchant_user.email) == 0

    def test_lockout_is_case_insensitive(self, client, merchant_user):
        for _ in range(5):
            _fail_login(client, merchant_user.email.upper())
        assert LockoutService.locked_seconds_remaining(merchant_user.email) > 0


@pytest.mark.django_db
class TestPasswordReset:
    def test_request_sends_signed_link_for_known_user(self, client, merchant_user):
        response = client.post("/password-reset/", {"email": merchant_user.email})
        assert response.status_code == 200
        assert len(mail.outbox) == 1
        match = re.search(r"/password-reset/confirm/\S+/\S+/", mail.outbox[0].body)
        assert match, "reset email must contain the confirm link"

    def test_request_is_indistinguishable_for_unknown_email(self, client):
        response = client.post("/password-reset/", {"email": "ghost@example.com"})
        assert response.status_code == 200
        assert b"If an account exists" in response.content
        assert len(mail.outbox) == 0

    def test_confirm_changes_password_and_revokes_sessions(self, client, merchant_user):
        SessionService.track(merchant_user, session_key="abc123", ip_address="127.0.0.1")
        client.post("/password-reset/", {"email": merchant_user.email})
        link = re.search(r"/password-reset/confirm/(\S+)/(\S+)/", mail.outbox[0].body)
        uidb64, token = link.group(1), link.group(2)

        response = client.get(f"/password-reset/confirm/{uidb64}/{token}/")
        assert response.status_code == 200

        response = client.post(
            f"/password-reset/confirm/{uidb64}/{token}/",
            {"password": "NewPassphrase!456", "confirm_password": "NewPassphrase!456"},
        )
        assert response.status_code == 200
        assert b"Password updated" in response.content

        merchant_user.refresh_from_db()
        assert merchant_user.check_password("NewPassphrase!456")
        assert not UserSession.objects.filter(user=merchant_user, revoked_at__isnull=True).exists()

        # The link is single-use: the token embeds the old password hash.
        response = client.post(
            f"/password-reset/confirm/{uidb64}/{token}/",
            {"password": "AnotherPass!789", "confirm_password": "AnotherPass!789"},
        )
        assert response.status_code == 400
        merchant_user.refresh_from_db()
        assert merchant_user.check_password("NewPassphrase!456")

    def test_garbage_token_is_rejected(self, client):
        response = client.get("/password-reset/confirm/MQ/0xdeadbeef/")
        assert response.status_code == 200
        assert b"invalid or has already been used" in response.content


def _signed_webhook(client, payload: dict, secret: str, timestamp: int | None = None):
    # Official scheme (verified 17 Aug 2026): HMAC over timestamp + raw body,
    # no separator; timestamp may be seconds or milliseconds.
    body = json.dumps(payload).encode()
    ts = str(timestamp or int(timezone.now().timestamp()))
    signature = base64.b64encode(
        hmac.new(secret.encode(), ts.encode() + body, hashlib.sha256).digest()
    ).decode()
    return client.post(
        "/webhooks/cashfree/",
        data=body,
        content_type="application/json",
        HTTP_X_WEBHOOK_TIMESTAMP=ts,
        HTTP_X_WEBHOOK_SIGNATURE=signature,
    )


def _approved_order(merchant_user, operations_user, admin_user, catalog_seeder):
    catalog_seeder()
    application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
    complete_required_draft(application)
    MerchantOnboardingService.submit(application, actor=merchant_user)
    MerchantOnboardingService.start_review(application, actor=admin_user)
    MerchantOnboardingService.approve(application, actor=admin_user)
    merchant = application.merchant
    merchant.agreement_status = Merchant.VerificationState.VERIFIED
    merchant.commercial_status = Merchant.CommercialStatus.ACTIVE
    merchant.save(update_fields=["agreement_status", "commercial_status"])
    from catalog.models import VoucherProduct

    product = VoucherProduct.objects.first()
    order = PaymentOrderService.create(merchant=merchant, actor=merchant_user, product=product, quantity=1)
    PaymentOrderService.submit(order, actor=merchant_user)
    PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
    PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=operations_user)
    return order


def _payment_payload(order, event_id="evt-1"):
    return {
        "event_id": event_id,
        "type": "PAYMENT_SUCCESS_WEBHOOK",
        "data": {
            "order": {"order_id": order.public_id, "order_amount": str(order.total)},
            "cf_payment_id": f"cf-{event_id}",
        },
    }


@pytest.fixture
def catalog_seeder():
    def seed():
        from decimal import Decimal

        from catalog.models import Brand, ServiceType, VoucherProduct

        service, _ = ServiceType.objects.get_or_create(
            code="BRANDED_VOUCHER", defaults={"name": "Branded Voucher", "is_active": True}
        )
        brand, _ = Brand.objects.get_or_create(
            slug="amazon", defaults={"name": "Amazon", "service_type": service}
        )
        VoucherProduct.objects.get_or_create(
            brand=brand,
            denomination=Decimal("1000.00"),
            defaults={"name": "Amazon 1000", "fee_rate": Decimal("0.02"), "tax_rate": Decimal("0.18")},
        )

    return seed


@pytest.mark.django_db
class TestCashfreeWebhook:
    def test_rejects_when_unconfigured(self, client):
        response = client.post("/webhooks/cashfree/", data=b"{}", content_type="application/json")
        assert response.status_code == 503

    @override_settings(CASHFREE_WEBHOOK_SECRET="whsec")
    def test_rejects_bad_signature(self, client):
        response = client.post(
            "/webhooks/cashfree/",
            data=b"{}",
            content_type="application/json",
            HTTP_X_WEBHOOK_TIMESTAMP=str(int(timezone.now().timestamp())),
            HTTP_X_WEBHOOK_SIGNATURE="bogus",
        )
        assert response.status_code == 401
        assert WebhookEvent.objects.count() == 0

    @override_settings(CASHFREE_WEBHOOK_SECRET="whsec")
    def test_rejects_stale_timestamp(
        self, client, merchant_user, operations_user, admin_user, catalog_seeder
    ):
        order = _approved_order(merchant_user, operations_user, admin_user, catalog_seeder)
        stale = int(timezone.now().timestamp()) - 3600
        response = _signed_webhook(client, _payment_payload(order), "whsec", timestamp=stale)
        assert response.status_code == 401

    @override_settings(CASHFREE_WEBHOOK_SECRET="whsec")
    def test_payment_success_is_ignored(
        self, client, merchant_user, operations_user, admin_user, catalog_seeder
    ):
        order = _approved_order(merchant_user, operations_user, admin_user, catalog_seeder)
        response = _signed_webhook(client, _payment_payload(order), "whsec")
        assert response.status_code == 200
        assert response.json()["detail"] == "ignored"
        order.refresh_from_db()
        assert order.status == OrderStatus.APPROVED
        event = WebhookEvent.objects.get(event_id="evt-1")
        assert event.signature_valid
        assert event.processing_result == "ignored"

    @override_settings(CASHFREE_WEBHOOK_SECRET="whsec")
    def test_duplicate_event_is_idempotent(
        self, client, merchant_user, operations_user, admin_user, catalog_seeder
    ):
        order = _approved_order(merchant_user, operations_user, admin_user, catalog_seeder)
        first = _signed_webhook(client, _payment_payload(order), "whsec")
        assert first.json()["detail"] == "ignored"
        duplicate = _signed_webhook(client, _payment_payload(order), "whsec")
        assert duplicate.status_code == 200
        assert duplicate.json()["detail"] == "Duplicate event ignored."
        assert WebhookEvent.objects.filter(event_id="evt-1").count() == 1
        order.refresh_from_db()
        assert order.status == OrderStatus.APPROVED


@pytest.mark.django_db
class TestHealthEndpoints:
    def test_healthz(self, client):
        assert client.get("/healthz/").status_code == 200

    def test_readyz(self, client):
        response = client.get("/readyz/")
        assert response.status_code == 200
        assert response.json()["checks"] == {"database": True, "cache": True}


@pytest.mark.django_db
class TestNotificationPreferences:
    def test_opted_out_user_gets_inapp_but_no_email(self, merchant_user):
        NotificationPreference.objects.create(user=merchant_user, email_enabled=False)
        notice = NotificationService.notify(
            user=merchant_user, title="Order update", body="Your order moved."
        )
        assert notice.pk
        assert len(mail.outbox) == 0

    def test_always_on_template_bypasses_opt_out(self, merchant_user):
        NotificationPreference.objects.create(user=merchant_user, email_enabled=False)
        NotificationService.notify(
            user=merchant_user,
            title="Security",
            body="A session was revoked.",
            template="session_revoked",
        )
        assert len(mail.outbox) == 1


class TestPostalService:
    def test_valid_pincode_returns_geography_and_caches(self):
        from integrations.postal import PostalService

        class FakeClient:
            calls = 0

            def json_request(self, method, url, **kwargs):
                self.calls += 1
                return 200, [
                    {
                        "Status": "Success",
                        "PostOffice": [{"Name": "Jaipur GPO", "District": "Jaipur", "State": "Rajasthan"}],
                    }
                ]

        client = FakeClient()
        result = PostalService.lookup("302001", client=client)
        assert result["state"] == "Rajasthan"
        assert result["district"] == "Jaipur"
        again = PostalService.lookup("302001", client=client)
        assert again == result
        assert client.calls == 1

    def test_invalid_pincode_format(self):
        from django.core.exceptions import ValidationError

        from integrations.postal import PostalService

        with pytest.raises(ValidationError):
            PostalService.lookup("1234")

    def test_unknown_pincode(self):
        from django.core.exceptions import ValidationError

        from integrations.postal import PostalService

        class EmptyClient:
            def json_request(self, method, url, **kwargs):
                return 200, [{"Status": "Error", "PostOffice": None}]

        with pytest.raises(ValidationError):
            PostalService.lookup("999999", client=EmptyClient())
