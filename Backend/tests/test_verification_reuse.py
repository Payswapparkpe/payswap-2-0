"""30-day verification reuse boundary tests (timezone-aware, UTC internally)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from integrations.cashfree import CashfreeClient
from merchants.services import MerchantOnboardingService
from verification.models import VerificationRecord
from verification.providers import CashfreeVerificationProvider
from verification.services import VerificationService


class FakeHttp:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def json_request(self, method, url, *, headers=None, json=None, files=None, timeout=20):
        self.calls.append({"method": method, "url": url, "json": json})
        return 200, self.responses.get("default", {"status": "SUCCESS"})


def _pan_provider(monkeypatch):
    http = FakeHttp({"default": {"pan_status": "VALID", "name": "ABC PRIVATE LIMITED", "reference_id": 900}})
    client = CashfreeClient(client_id="id", client_secret="sec", environment="sandbox", http=http)
    provider = CashfreeVerificationProvider(client)
    monkeypatch.setattr(VerificationService, "provider", staticmethod(lambda: provider))
    return http


def _age(record, *, days: float):
    """Backdate a verified record as if completed `days` ago."""
    record.completed_at = timezone.now() - timedelta(days=days)
    record.expires_at = record.completed_at + VerificationService.cache_window()
    record.save(update_fields=["completed_at", "expires_at"])


@pytest.mark.django_db
class TestReuseBoundaries:
    PAN = "ABCDE1234F"

    def _verify(self, merchant, user):
        return VerificationService.verify_pan(
            merchant=merchant, actor=user, pan=self.PAN, name="ABC PRIVATE LIMITED", dob="1990-01-01"
        )

    @pytest.fixture
    def merchant(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        return application.merchant

    def test_day_zero_reuses(self, merchant, merchant_user, monkeypatch):
        http = _pan_provider(monkeypatch)
        first = self._verify(merchant, merchant_user)
        second = self._verify(merchant, merchant_user)
        assert second.reused_from_id == first.id
        assert len(http.calls) == 1

    def test_day_29_reuses(self, merchant, merchant_user, monkeypatch):
        http = _pan_provider(monkeypatch)
        first = self._verify(merchant, merchant_user)
        _age(first, days=29)
        second = self._verify(merchant, merchant_user)
        assert second.reused_from_id == first.id
        assert len(http.calls) == 1

    def test_day_30_exact_boundary_is_fresh(self, merchant, merchant_user, monkeypatch):
        """At the exact expiry instant the record is stale (exclusive boundary)."""
        http = _pan_provider(monkeypatch)
        first = self._verify(merchant, merchant_user)
        _age(first, days=30)
        second = self._verify(merchant, merchant_user)
        assert second.reused_from_id is None
        assert len(http.calls) == 2

    def test_day_31_is_fresh(self, merchant, merchant_user, monkeypatch):
        http = _pan_provider(monkeypatch)
        first = self._verify(merchant, merchant_user)
        _age(first, days=31)
        second = self._verify(merchant, merchant_user)
        assert second.reused_from_id is None
        assert len(http.calls) == 2

    def test_reuse_copy_is_never_a_source(self, merchant, merchant_user, monkeypatch):
        http = _pan_provider(monkeypatch)
        first = self._verify(merchant, merchant_user)
        copy = self._verify(merchant, merchant_user)
        third = self._verify(merchant, merchant_user)
        assert third.reused_from_id == first.id
        assert third.reused_from_id != copy.id
        assert len(http.calls) == 1

    def test_failed_verification_is_never_reused(self, merchant, merchant_user, monkeypatch):
        http = _pan_provider(monkeypatch)
        first = self._verify(merchant, merchant_user)
        first.status = VerificationRecord.Status.FAILED
        first.save(update_fields=["status"])
        second = self._verify(merchant, merchant_user)
        assert second.reused_from_id is None
        assert len(http.calls) == 2

    def test_reuse_scoped_to_merchant(self, merchant, merchant_user, other_merchant_user, monkeypatch):
        _pan_provider(monkeypatch)
        self._verify(merchant, merchant_user)
        other_app = MerchantOnboardingService.start(other_merchant_user, entity_type="PRIVATE_LIMITED")
        record = VerificationService.verify_pan(
            merchant=other_app.merchant,
            actor=other_merchant_user,
            pan=self.PAN,
            name="ABC PRIVATE LIMITED",
            dob="1990-01-01",
        )
        assert record.reused_from_id is None

    def test_user_safe_reason_strips_provider_payload(self):
        from integrations.cashfree import CashfreeError
        from verification.services import SAFE_INVALID, SAFE_UNAVAILABLE, user_safe_reason

        assert user_safe_reason(CashfreeError("IP not whitelisted", code="ip_error")) == SAFE_UNAVAILABLE
        assert user_safe_reason("raw cashfree dump") == SAFE_INVALID

    def test_reused_record_carries_audit_fields(self, merchant, merchant_user, monkeypatch):
        _pan_provider(monkeypatch)
        first = self._verify(merchant, merchant_user)
        second = self._verify(merchant, merchant_user)
        assert second.reuse_reason == "within_cache_window"
        assert second.reused_at is not None
        assert second.expires_at == first.expires_at

    def test_daily_attempt_cap_blocks_fresh_calls(self, merchant, merchant_user, monkeypatch):
        """Reuses don't count; the 6th fresh provider call in a day is rejected."""
        from django.core.exceptions import ValidationError

        http = _pan_provider(monkeypatch)
        first = self._verify(merchant, merchant_user)
        for attempt in range(4):
            _age(first, days=31)  # expire the source so each attempt is fresh
            first = self._verify(merchant, merchant_user)
        _age(first, days=31)
        with pytest.raises(ValidationError, match="Too many verification attempts"):
            self._verify(merchant, merchant_user)
        assert len(http.calls) == 5
