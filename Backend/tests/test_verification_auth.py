from datetime import timedelta

import pytest
from django.core import mail

from accounts.models import RecoveryCode, SecurityCredential
from accounts.services import (
    MfaService,
    MpinService,
    SessionService,
    StepUpService,
    VerificationService,
)


@pytest.mark.django_db
class TestContactVerification:
    def test_email_code_verifies_and_is_single_use(self, merchant_user):
        challenge = VerificationService.issue(merchant_user, channel="email")
        assert merchant_user.email_verified_at is None
        assert mail.outbox
        assert "verification code" in mail.outbox[0].subject.lower()
        code = challenge.debug_code
        assert VerificationService.confirm(merchant_user, channel="email", code=code)
        merchant_user.refresh_from_db()
        assert merchant_user.email_verified_at is not None
        with pytest.raises(Exception):
            VerificationService.confirm(merchant_user, channel="email", code=code)

    def test_wrong_code_is_rejected(self, merchant_user):
        VerificationService.issue(merchant_user, channel="mobile")
        assert VerificationService.confirm(merchant_user, channel="mobile", code="000000") is False
        merchant_user.refresh_from_db()
        assert merchant_user.mobile_verified_at is None

    def test_resend_cooldown_blocks_immediate_reissue(self, merchant_user):
        VerificationService.issue(merchant_user, channel="email")
        with pytest.raises(Exception, match="Wait"):
            VerificationService.issue(merchant_user, channel="email")

    def test_expired_code_is_rejected(self, merchant_user):
        challenge = VerificationService.issue(merchant_user, channel="email").challenge
        challenge.expires_at = challenge.expires_at - timedelta(hours=1)
        challenge.save(update_fields=["expires_at"])
        assert VerificationService.confirm(merchant_user, channel="email", code="123456") is False

    def test_attempt_limit_locks_challenge(self, merchant_user):
        challenge = VerificationService.issue(merchant_user, channel="email").challenge
        challenge.max_attempts = 2
        challenge.save(update_fields=["max_attempts"])
        assert VerificationService.confirm(merchant_user, channel="email", code="000000") is False
        assert VerificationService.confirm(merchant_user, channel="email", code="000000") is False
        challenge.refresh_from_db()
        assert VerificationService.confirm(merchant_user, channel="email", code="999999") is False
        assert challenge.attempts == 2

    def test_destination_is_masked(self, merchant_user):
        challenge = VerificationService.issue(merchant_user, channel="email").challenge
        assert "@" in challenge.destination_masked
        assert "***" in challenge.destination_masked
        assert merchant_user.email not in challenge.destination_masked

    def test_test_otp_accepted_only_in_test_mode(self, merchant_user, settings):
        settings.AUTH_TEST_MODE = True
        settings.TEST_OTP = "123456"
        VerificationService.issue(merchant_user, channel="email")
        assert VerificationService.confirm(merchant_user, channel="email", code="123456") is True

    def test_test_otp_rejected_when_test_mode_off(self, merchant_user, settings):
        settings.AUTH_TEST_MODE = False
        settings.TEST_OTP = "123456"
        VerificationService.issue(merchant_user, channel="email")
        assert VerificationService.confirm(merchant_user, channel="email", code="123456") is False

    def test_purpose_isolated_challenges(self, merchant_user):
        VerificationService.issue(merchant_user, channel="email")
        other = VerificationService.issue(merchant_user, channel="email", purpose="security_action")
        assert (
            VerificationService.confirm(
                merchant_user, channel="email", code=other.debug_code, purpose="security_action"
            )
            is True
        )


@pytest.mark.django_db
class TestMfaAndStepUp:
    def test_totp_enrol_and_verify(self, admin_user):
        device, secret = MfaService.enrol(admin_user)
        token = MfaService.current_token(secret)
        assert MfaService.verify(admin_user, token)
        admin_user.refresh_from_db()
        device.refresh_from_db()
        assert admin_user.mfa_enforced is True
        assert device.confirmed is True

    def test_step_up_expires(self, admin_user):
        assert StepUpService.is_satisfied(admin_user, session={"_step_up_at": 0}) is False
        session = {}
        StepUpService.mark(session)
        assert StepUpService.is_satisfied(admin_user, session=session) is True

    def test_revoke_session(self, admin_user):
        tracked = SessionService.track(
            admin_user, session_key="abc123", ip_address="127.0.0.1", user_agent="pytest"
        )
        SessionService.revoke(tracked, actor=admin_user)
        tracked.refresh_from_db()
        assert tracked.revoked_at is not None


@pytest.mark.django_db
class TestMpin:
    def test_set_and_verify(self, merchant_user):
        MpinService.set(merchant_user, "482910")
        credential = SecurityCredential.objects.get(user=merchant_user)
        assert credential.mpin_enabled is True
        assert credential.mpin_hash.startswith("$argon2id$")
        assert "482910" not in credential.mpin_hash
        assert MpinService.verify(merchant_user, "482910") is True
        assert MpinService.verify(merchant_user, "000000") is False

    def test_invalid_format_rejected(self, merchant_user):
        with pytest.raises(Exception):
            MpinService.set(merchant_user, "12ab")
        with pytest.raises(Exception):
            MpinService.set(merchant_user, "12345678")

    def test_lockout_after_failures(self, merchant_user):
        MpinService.set(merchant_user, "246813")
        for _ in range(5):
            assert MpinService.verify(merchant_user, "111111") is False
        credential = SecurityCredential.objects.get(user=merchant_user)
        assert credential.mpin_locked_until is not None
        with pytest.raises(Exception, match="Too many"):
            MpinService.verify(merchant_user, "246813")

    def test_change_requires_current(self, merchant_user):
        MpinService.set(merchant_user, "135791")
        with pytest.raises(Exception, match="current MPIN"):
            MpinService.change(merchant_user, "000000", "999888")
        MpinService.change(merchant_user, "135791", "999888")
        assert MpinService.verify(merchant_user, "999888") is True


@pytest.mark.django_db
class TestRecoveryCodes:
    def test_generate_and_single_use(self, merchant_user):
        codes = MfaService.generate_recovery_codes(merchant_user)
        assert len(codes) == 8
        assert RecoveryCode.objects.filter(user=merchant_user, used_at__isnull=True).count() == 8
        assert not RecoveryCode.objects.filter(user=merchant_user).first().code_hash == codes[0]
        assert MfaService.verify_recovery_code(merchant_user, codes[0]) is True
        assert MfaService.verify_recovery_code(merchant_user, codes[0]) is False

    def test_regeneration_invalidates_old_codes(self, merchant_user):
        old_codes = MfaService.generate_recovery_codes(merchant_user)
        MfaService.generate_recovery_codes(merchant_user)
        assert MfaService.verify_recovery_code(merchant_user, old_codes[0]) is False
