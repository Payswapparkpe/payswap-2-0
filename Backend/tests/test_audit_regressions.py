from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from audit.models import AuditEvent
from catalog.models import Brand, ServiceType, VoucherProduct
from merchants.models import Merchant
from merchants.services import MerchantOnboardingService
from orders.models import OrderStatus
from orders.services import PaymentOrderService
from tests.support import complete_required_draft


@pytest.fixture
def submitted_order(merchant_user, admin_user):
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
        slug="audit-amazon", defaults={"name": "Audit Amazon", "service_type": service}
    )
    product, _ = VoucherProduct.objects.get_or_create(
        brand=brand,
        denomination=Decimal("1000.00"),
        defaults={"name": "Audit Amazon ₹1,000", "fee_rate": Decimal("0.02"), "tax_rate": Decimal("0.18")},
    )
    order = PaymentOrderService.create(merchant=merchant, actor=merchant_user, product=product, quantity=1)
    PaymentOrderService.submit(order, actor=merchant_user)
    return order


@pytest.mark.django_db
class TestAuditRegressions:
    def test_cookie_consent_only_returns_to_the_same_site(self, client):
        response = client.post(
            "/legal/cookies/consent/",
            {"consent": "all"},
            HTTP_REFERER="https://phishing.invalid/sign-in",
        )

        assert response.status_code == 302
        assert response.url == "/"

    def test_logout_is_post_only(self, client, merchant_user):
        client.force_login(merchant_user)

        assert client.get("/logout/").status_code == 405
        assert client.post("/logout/").status_code == 302

    def test_kyc_employee_cannot_view_or_transition_orders(self, client, kyc_user, submitted_order):
        client.force_login(kyc_user)

        assert client.get(f"/employee/orders/{submitted_order.public_id}/").status_code == 403
        assert (
            client.post(f"/employee/orders/{submitted_order.public_id}/", {"action": "review"}).status_code
            == 403
        )
        submitted_order.refresh_from_db()
        assert submitted_order.status == OrderStatus.SUBMITTED

    def test_kyc_employee_order_list_does_not_expose_order_references(
        self, client, kyc_user, submitted_order
    ):
        client.force_login(kyc_user)

        response = client.get("/employee/orders/")

        assert response.status_code == 200
        assert submitted_order.public_id.encode() not in response.content

    def test_order_builder_handles_tampered_query_parameters(self, client, merchant_user):
        MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        client.force_login(merchant_user)

        response = client.get("/merchant/orders/new/?step=5&product=not-an-id&quantity=not-a-number")

        assert response.status_code == 200
        assert b"Select brand / voucher" in response.content

    def test_order_builder_rejects_inactive_products(self, client, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        service = ServiceType.objects.create(code="INACTIVE", name="Inactive", is_active=False)
        brand = Brand.objects.create(name="Inactive brand", slug="inactive-brand", service_type=service)
        product = VoucherProduct.objects.create(
            brand=brand,
            denomination=Decimal("100.00"),
            name="Inactive voucher",
            is_active=False,
        )
        client.force_login(merchant_user)

        response = client.post("/merchant/orders/new/", {"product": product.pk, "quantity": "1"})

        assert response.status_code == 404
        assert application.merchant.orders.count() == 0

    def test_security_actions_are_audited(self, client, admin_user, kyc_user):
        client.force_login(admin_user)

        response = client.post(f"/administration/security/users/{kyc_user.pk}/", {"action": "force_logout"})

        assert response.status_code == 302
        assert AuditEvent.objects.filter(
            actor=admin_user,
            action="security.force_logout",
            resource_type="user",
            resource_id=str(kyc_user.pk),
        ).exists()

    def test_legal_disclosure_uses_configured_contact(self, client):
        with override_settings(
            LEGAL_ENTITY_NAME="Payswap Fintech Private Limited",
            GRIEVANCE_OFFICER_NAME="Asha Sharma, Grievance Officer",
            GRIEVANCE_EMAIL="grievance@example.test",
            GRIEVANCE_POSTAL_ADDRESS="1 Example Road, Mumbai 400001",
        ):
            response = client.get("/legal/grievance/")

        assert response.status_code == 200
        assert b"Asha Sharma, Grievance Officer" in response.content
        assert b"grievance@example.test" in response.content
        assert b"1 Example Road, Mumbai 400001" in response.content

    def test_status_charts_expose_values_to_assistive_technology(self, client, admin_user, merchant_user):
        Merchant.objects.create(
            public_id="PSM-AUDIT-001",
            owner=merchant_user,
            business_name="Audit merchant",
            entity_type="PRIVATE_LIMITED",
        )
        client.force_login(admin_user)

        response = client.get("/administration/")

        assert response.status_code == 200
        assert b'role="list"' in response.content
        assert b'role="listitem"' in response.content
        assert b'aria-hidden="true"' in response.content
        assert b"the number is the exact count" in response.content

    def test_local_bootstrap_requires_an_explicit_password(self):
        with pytest.raises(CommandError):
            call_command("bootstrap_local")
