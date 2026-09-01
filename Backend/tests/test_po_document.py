"""Purchase order A4 document: context completeness, rendering, access control."""

from decimal import Decimal

import pytest

from audit.models import AuditEvent
from catalog.models import Brand, ServiceType, VoucherProduct
from merchants.models import Merchant
from merchants.services import MerchantOnboardingService
from orders.document import amount_in_words, po_document_context, render_po_pdf
from orders.services import PaymentOrderService
from tests.support import complete_required_draft


def _activated_merchant(merchant_user, admin_user):
    application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
    complete_required_draft(application)
    MerchantOnboardingService.submit(application, actor=merchant_user)
    MerchantOnboardingService.start_review(application, actor=admin_user)
    MerchantOnboardingService.approve(application, actor=admin_user)
    merchant = application.merchant
    merchant.commercial_status = Merchant.CommercialStatus.ACTIVE
    merchant.agreement_status = Merchant.VerificationState.VERIFIED
    merchant.save(update_fields=["commercial_status", "agreement_status"])
    return merchant


def _product():
    service, _ = ServiceType.objects.get_or_create(
        code="BRANDED_VOUCHER", defaults={"name": "Branded Voucher", "is_active": True}
    )
    brand, _ = Brand.objects.get_or_create(
        slug="swiggy", defaults={"name": "Swiggy", "service_type": service}
    )
    product, _ = VoucherProduct.objects.get_or_create(
        brand=brand,
        denomination=Decimal("500.00"),
        defaults={"name": "Swiggy ₹500", "fee_rate": Decimal("0.02"), "tax_rate": Decimal("0.18")},
    )
    return product


def _order(merchant_user, admin_user, quantity=2):
    merchant = _activated_merchant(merchant_user, admin_user)
    return PaymentOrderService.create(
        merchant=merchant, actor=merchant_user, product=_product(), quantity=quantity
    )


@pytest.mark.django_db
class TestAmountInWords:
    def test_zero(self):
        assert amount_in_words(Decimal("0")) == "Rupees Zero Only"

    def test_simple(self):
        assert amount_in_words(Decimal("100")) == "Rupees One Hundred Only"

    def test_paise(self):
        assert amount_in_words(Decimal("2040.80")) == ("Rupees Two Thousand Forty and Eighty Paise Only")

    def test_indian_numbering(self):
        assert amount_in_words(Decimal("123456")) == (
            "Rupees One Lakh Twenty Three Thousand Four Hundred Fifty Six Only"
        )

    def test_crore(self):
        assert amount_in_words(Decimal("10000000")) == "Rupees One Crore Only"


@pytest.mark.django_db
class TestPoDocumentContext:
    """Every standard PO field must be present on the generated document."""

    def test_all_standard_fields_present(self, merchant_user, admin_user):
        order = _order(merchant_user, admin_user, quantity=2)
        ctx = po_document_context(order)
        assert ctx["po_number"] == order.public_id
        assert ctx["po_date"]
        assert ctx["revision"] == 1
        assert ctx["status"] == "Draft"
        assert ctx["currency"] == "INR"
        assert ctx["product_name"] == "Swiggy ₹500"
        assert ctx["brand_name"] == "Swiggy"
        assert ctx["denomination"] == Decimal("500.00")
        assert ctx["quantity"] == 2
        assert ctx["subtotal"] == Decimal("1000.00")
        assert ctx["fees"] == Decimal("20.00")
        assert ctx["tax"] == Decimal("3.60")
        assert ctx["total"] == Decimal("1023.60")
        assert ctx["total_words"] == ("Rupees One Thousand Twenty Three and Sixty Paise Only")
        assert ctx["hsn"] == "4907"
        assert ctx["created_by"]
        assert ctx["approved_line"] == "Approval: pending"
        # Parties
        assert ctx["buyer"]["merchant_id"] == order.merchant.public_id
        assert ctx["buyer"]["legal_name"]
        assert ctx["buyer"]["signatory_name"]
        # Compliance text
        assert len(ctx["terms"]) >= 8
        assert any("GST" in term for term in ctx["terms"])
        assert any("Governed by the laws of India" in term for term in ctx["terms"])

    def test_context_reflects_current_revision_after_amend(self, merchant_user, admin_user, operations_user):
        from orders.models import OrderStatus

        order = _order(merchant_user, admin_user, quantity=2)
        PaymentOrderService.submit(order, actor=merchant_user)
        PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=operations_user)
        PaymentOrderService.transition(order, OrderStatus.APPROVED, actor=operations_user)
        PaymentOrderService.amend(order, actor=merchant_user, product=_product(), quantity=4)
        order.refresh_from_db()
        ctx = po_document_context(order)
        assert ctx["revision"] == 2
        assert ctx["quantity"] == 4
        assert ctx["total"] == Decimal("2047.20")
        assert ctx["approved_line"].startswith("Approved by:")

    def test_pdf_bytes_are_generated(self, merchant_user, admin_user):
        order = _order(merchant_user, admin_user)
        content = render_po_pdf(order)
        assert content[:5] == b"%PDF-"
        assert len(content) > 3000

    def test_company_identifiers_come_from_settings(self, merchant_user, admin_user, settings):
        settings.COMPANY_GSTIN = "08ABCDE1234F1Z5"
        settings.COMPANY_PAN = "ABCDE1234F"
        ctx = po_document_context(_order(merchant_user, admin_user))
        assert ctx["company_gstin"] == "08ABCDE1234F1Z5"
        assert ctx["company_pan"] == "ABCDE1234F"


@pytest.mark.django_db
class TestPoDocumentAccess:
    def test_merchant_downloads_own_order_audited(self, client, merchant_user, admin_user):
        order = _order(merchant_user, admin_user)
        client.force_login(merchant_user)
        response = client.post(f"/merchant/orders/{order.public_id}/document/")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert f"PO-{order.public_id}" in response["Content-Disposition"]
        assert AuditEvent.objects.filter(
            action="order.document_download", resource_id=order.public_id
        ).exists()

    def test_get_is_not_allowed(self, client, merchant_user, admin_user):
        order = _order(merchant_user, admin_user)
        client.force_login(merchant_user)
        assert client.get(f"/merchant/orders/{order.public_id}/document/").status_code == 405

    def test_other_merchant_is_denied(self, client, merchant_user, admin_user, other_merchant_user):
        order = _order(merchant_user, admin_user)
        Merchant.objects.create(
            owner=other_merchant_user,
            public_id="PSM-009999",
            business_name="Other",
            status="ACTIVE",
        )
        client.force_login(other_merchant_user)
        response = client.post(f"/merchant/orders/{order.public_id}/document/")
        assert response.status_code == 403

    def test_staff_with_order_view_can_download(self, client, merchant_user, admin_user, operations_user):
        order = _order(merchant_user, admin_user)
        client.force_login(operations_user)
        response = client.post(f"/employee/orders/{order.public_id}/document/")
        assert response.status_code == 200

    def test_anonymous_is_redirected_to_login(self, client, merchant_user, admin_user):
        order = _order(merchant_user, admin_user)
        response = client.post(f"/merchant/orders/{order.public_id}/document/")
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_unknown_order_404(self, client, merchant_user):
        client.force_login(merchant_user)
        assert client.post("/merchant/orders/ORD-999999/document/").status_code == 404
