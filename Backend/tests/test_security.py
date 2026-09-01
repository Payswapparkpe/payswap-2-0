import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from access.policy import Policy
from merchants.services import MerchantOnboardingService
from orders.models import OrderStatus
from orders.services import PaymentOrderService
from tests.support import complete_required_draft
from verification.models import Document
from verification.services import DocumentReviewService


@pytest.mark.django_db
class TestSecurityAcceptance:
    def test_merchant_cannot_approve_kyc(self, merchant_user):
        assert not Policy.can(merchant_user, "kyc.approve")
        with pytest.raises(PermissionDenied):
            Policy.require(merchant_user, "kyc.approve")

    def test_employee_cannot_manage_roles(self, kyc_user):
        assert not Policy.can(kyc_user, "role.manage")

    def test_document_idor(self, client, merchant_user, other_merchant_user):
        own = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        other = MerchantOnboardingService.start(other_merchant_user, entity_type="PRIVATE_LIMITED")
        document = DocumentReviewService.register_upload(
            merchant=other.merchant,
            actor=other_merchant_user,
            doc_type=Document.DocType.PAN,
            uploaded_file=SimpleUploadedFile("pan.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        )
        client.force_login(merchant_user)
        response = client.get(f"/administration/merchants/{other.merchant.public_id}/")
        assert response.status_code == 403
        assert document.merchant_id != own.merchant.id

    def test_merchant_cannot_cancel_after_approved(
        self, merchant_user, admin_user, operations_user
    ):
        from decimal import Decimal

        from catalog.models import Brand, ServiceType, VoucherProduct
        from merchants.models import Merchant

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
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
        PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=operations_user)
        order.refresh_from_db()
        with pytest.raises(ValidationError):
            PaymentOrderService.cancel(order, actor=merchant_user)

    def test_document_download_idor(self, client, merchant_user, other_merchant_user):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from merchants.services import MerchantOnboardingService
        from verification.models import Document
        from verification.services import DocumentReviewService

        MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        other = MerchantOnboardingService.start(other_merchant_user, entity_type="PRIVATE_LIMITED")
        document = DocumentReviewService.register_upload(
            merchant=other.merchant,
            actor=other_merchant_user,
            doc_type=Document.DocType.PAN,
            uploaded_file=SimpleUploadedFile("pan.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        )
        client.force_login(merchant_user)
        get_response = client.get(f"/merchant/documents/{document.public_id}/download/")
        assert get_response.status_code == 405
        response = client.post(f"/merchant/documents/{document.public_id}/download/")
        assert response.status_code == 403
