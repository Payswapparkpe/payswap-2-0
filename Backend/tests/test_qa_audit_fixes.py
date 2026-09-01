import pytest
from django.contrib.sessions.models import Session
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings

from access.models import UserRole
from accounts.models import UserSession, VerificationChallenge
from accounts.services import SessionService
from core.crypto import encrypt_text
from merchants.services import MerchantOnboardingService
from portals.search import search
from tests.support import complete_required_draft
from verification.models import Document
from verification.services import DocumentReviewService, validate_document_file


@pytest.mark.django_db
class TestQaAuditFixes:
    def test_bootstrap_grants_portal_roles(self, access_seed):
        call_command("bootstrap_local", password="CorrectHorse9!")
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.get(email="merchant@payswap.local")
        assert UserRole.objects.filter(user=user, role__slug="merchant").exists()

    def test_session_revoke_deletes_django_session(self, client, merchant_user):
        client.force_login(merchant_user)
        session_key = client.session.session_key
        tracked = SessionService.track(merchant_user, session_key=session_key)
        assert Session.objects.filter(session_key=session_key).exists()
        SessionService.revoke(tracked, actor=merchant_user)
        assert not Session.objects.filter(session_key=session_key).exists()
        tracked.refresh_from_db()
        assert tracked.revoked_at is not None

    def test_force_logout_ends_active_session(self, client, admin_user, kyc_user):
        other = client.__class__()
        other.force_login(kyc_user)
        session_key = other.session.session_key
        SessionService.track(kyc_user, session_key=session_key)
        client.force_login(admin_user)
        response = client.post(f"/administration/security/users/{kyc_user.pk}/", {"action": "force_logout"})
        assert response.status_code == 302
        assert not Session.objects.filter(session_key=session_key).exists()
        assert UserSession.objects.filter(user=kyc_user, revoked_at__isnull=True).count() == 0

    def test_html_upload_is_rejected(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        with pytest.raises(ValidationError):
            DocumentReviewService.register_upload(
                merchant=application.merchant,
                actor=merchant_user,
                doc_type=Document.DocType.PAN,
                uploaded_file=SimpleUploadedFile(
                    "malware.html", b"<script>alert(1)</script>", content_type="text/html"
                ),
            )

    def test_pdf_upload_is_accepted(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        document = DocumentReviewService.register_upload(
            merchant=application.merchant,
            actor=merchant_user,
            doc_type=Document.DocType.PAN,
            uploaded_file=SimpleUploadedFile("pan.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        )
        assert document.pk
        validate_document_file(
            SimpleUploadedFile("x.jpg", b"\xff\xd8\xff\xe0rest", content_type="image/jpeg")
        )

    def test_verify_get_does_not_issue_a_code(self, client, merchant_user):
        client.force_login(merchant_user)
        before = VerificationChallenge.objects.filter(user=merchant_user, channel="email").count()
        response = client.get("/merchant/verify/email/")
        assert response.status_code == 200
        after = VerificationChallenge.objects.filter(user=merchant_user, channel="email").count()
        assert after == before

    def test_onboarding_fields_round_trip(self, client, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)
        client.post(
            f"/merchant/onboarding/{application.public_id}/",
            {
                "action": "save",
                "step": "business",
                "legal_name": "Sharma Digital Services Private Limited",
                "cin": "U74999MH2018PTC123456",
                "pan": "ABCDE1234F",
                "gstin": "27ABCDE1234F1Z5",
                "confirmed": "on",
            },
        )
        html = client.get(f"/merchant/onboarding/{application.public_id}/?step=business").content.decode()
        assert "Sharma Digital Services Private Limited" in html
        assert "value=\"{'cin'" not in html
        assert "Legal name" in html

    def test_bank_step_stores_account_last4_only(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        step = MerchantOnboardingService.save_step(
            application,
            key="bank",
            actor=merchant_user,
            data={
                "account_holder": "Sharma Digital Services Private Limited",
                "account_number": "50100012345678",
                "ifsc": "HDFC0001234",
            },
        )
        assert step.data["account_number"] == "****5678"
        assert "50100012345678" not in str(step.data)

    def test_kyc_search_lists_orders(self, kyc_user, merchant_user, admin_user):
        from decimal import Decimal

        from catalog.models import Brand, ServiceType, VoucherProduct
        from merchants.models import Merchant
        from orders.services import PaymentOrderService

        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        complete_required_draft(application)
        MerchantOnboardingService.submit(application, actor=merchant_user)
        MerchantOnboardingService.start_review(application, actor=admin_user)
        MerchantOnboardingService.approve(application, actor=admin_user)
        merchant = application.merchant
        merchant.commercial_status = Merchant.CommercialStatus.ACTIVE
        merchant.agreement_status = Merchant.VerificationState.VERIFIED
        merchant.save(update_fields=["commercial_status", "agreement_status"])
        service, _ = ServiceType.objects.get_or_create(
            code="BRANDED_VOUCHER", defaults={"name": "Branded Voucher", "is_active": True}
        )
        brand, _ = Brand.objects.get_or_create(
            slug="amazon", defaults={"name": "Amazon", "service_type": service}
        )
        product, _ = VoucherProduct.objects.get_or_create(
            brand=brand,
            denomination=Decimal("1000.00"),
            defaults={"name": "Amazon ₹1,000", "fee_rate": Decimal("0.02"), "tax_rate": Decimal("0.18")},
        )
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=product, quantity=1
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        labels = " ".join(item["label"] for item in search(kyc_user, order.public_id))
        assert order.public_id in labels

    def test_login_page_does_not_load_datatables(self, client):
        html = client.get("/login/").content.decode()
        assert "dataTables.min.js" not in html

    def test_reset_mfa_deletes_totp_device(self, client, admin_user, kyc_user):
        from django_otp.plugins.otp_totp.models import TOTPDevice

        TOTPDevice.objects.create(user=kyc_user, name="authenticator", confirmed=True)
        kyc_user.mfa_enforced = True
        kyc_user.save(update_fields=["mfa_enforced"])
        client.force_login(admin_user)
        client.post(f"/administration/security/users/{kyc_user.pk}/", {"action": "reset_mfa"})
        kyc_user.refresh_from_db()
        assert kyc_user.mfa_enforced is False
        assert not TOTPDevice.objects.filter(user=kyc_user).exists()

    def test_fernet_rejects_padded_passphrase(self):
        with override_settings(FIELD_ENCRYPTION_KEY="short-passphrase"):
            with pytest.raises(ImproperlyConfigured):
                encrypt_text("secret")
