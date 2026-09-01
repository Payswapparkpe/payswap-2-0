"""P3 regression tests: server-side pagination, pincode autofill, profile edits."""

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError

from audit.models import AuditEvent
from merchants.models import Merchant
from merchants.privacy import decrypt_step_data
from merchants.services import MerchantOnboardingService


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _make_merchants(user_model, count, prefix):
    for index in range(count):
        owner = user_model.objects.create_user(
            email=f"{prefix}-{index}@payswap.test",
            password="CorrectHorse9!",
            user_type="MERCHANT",
        )
        Merchant.objects.create(
            owner=owner,
            public_id=f"PSM-P3-{prefix[:4].upper()}-{index:04d}",
            entity_type="INDIVIDUAL",
            business_name=f"{prefix} Co {index}",
        )


@pytest.mark.django_db
class TestServerPagination:
    def test_admin_merchant_list_paginates(self, client, admin_user, user_model):
        _make_merchants(user_model, 30, "pager")
        client.force_login(admin_user)
        first = client.get("/administration/merchants/")
        assert first.status_code == 200
        assert first.context["page"].number == 1
        assert first.context["page"].paginator.num_pages >= 2
        second = client.get("/administration/merchants/?page=2")
        assert second.status_code == 200
        assert second.context["page"].number == 2
        first_ids = {m.pk for m in first.context["merchants"]}
        second_ids = {m.pk for m in second.context["merchants"]}
        assert not first_ids & second_ids

    def test_pager_preserves_filters(self, client, admin_user, user_model):
        _make_merchants(user_model, 30, "filter")
        client.force_login(admin_user)
        response = client.get("/administration/merchants/?status=ACTIVE&page=2")
        assert response.status_code == 200
        assert "status=ACTIVE" in response.context["querystring"]
        assert "page=" not in response.context["querystring"]

    def test_out_of_range_page_clamps_to_last(self, client, admin_user, merchant_user):
        client.force_login(admin_user)
        response = client.get("/administration/merchants/?page=999")
        assert response.status_code == 200
        assert response.context["page"].number == 1

    def test_order_list_status_filter(self, client, admin_user):
        client.force_login(admin_user)
        response = client.get("/administration/orders/?status=APPROVED")
        assert response.status_code == 200
        assert list(response.context["orders"]) == []

    def test_audit_from_date_filter(self, client, admin_user):
        client.force_login(admin_user)
        response = client.get("/administration/audit/?from=2999-01-01")
        assert response.status_code == 200
        assert list(response.context["events"]) == []


@pytest.mark.django_db
class TestPincodeLookup:
    def test_endpoint_returns_geography(self, client, merchant_user, monkeypatch):
        monkeypatch.setattr(
            "portals.views.merchant.PostalService.lookup",
            staticmethod(
                lambda pin: {
                    "pincode": "560001",
                    "district": "Bengaluru",
                    "state": "Karnataka",
                    "area": "MG Road",
                }
            ),
        )
        client.force_login(merchant_user)
        response = client.get("/merchant/onboarding/pincode/?pin=560001")
        assert response.status_code == 200
        assert response.json()["state"] == "Karnataka"

    def test_endpoint_rejects_bad_pin(self, client, merchant_user, monkeypatch):
        def _raise(pin):
            raise ValidationError("This PIN code was not found.")

        monkeypatch.setattr("portals.views.merchant.PostalService.lookup", staticmethod(_raise))
        client.force_login(merchant_user)
        response = client.get("/merchant/onboarding/pincode/?pin=000000")
        assert response.status_code == 400
        assert "not found" in response.json()["error"]

    def test_endpoint_requires_merchant_auth(self, client):
        response = client.get("/merchant/onboarding/pincode/?pin=560001")
        assert response.status_code in (302, 403)

    def test_business_step_accepts_office_and_pincode(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        step = MerchantOnboardingService.save_step(
            application,
            key="business",
            actor=merchant_user,
            data={
                "legal_name": "Pin Test Pvt Ltd",
                "cin": "U72900KA2020PTC123456",
                "pan": "ABCDE1234F",
                "gstin": "29ABCDE1234F1Z5",
                "registered_office": "12 MG Road",
                "pincode": "560001",
            },
        )
        plain = decrypt_step_data(step.data)
        assert plain["registered_office"] == "12 MG Road"
        assert plain["pincode"] == "560001"

    def test_business_step_rejects_malformed_pincode(self, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        with pytest.raises(ValidationError):
            MerchantOnboardingService.save_step(
                application,
                key="business",
                actor=merchant_user,
                data={
                    "legal_name": "Pin Test Pvt Ltd",
                    "cin": "U72900KA2020PTC123456",
                    "pan": "ABCDE1234F",
                    "gstin": "29ABCDE1234F1Z5",
                    "pincode": "1234",
                },
            )


@pytest.mark.django_db
class TestAdminControls:
    def _merchant(self, user_model, email="control@payswap.test"):
        owner = user_model.objects.create_user(email=email, password="CorrectHorse9!", user_type="MERCHANT")
        return Merchant.objects.create(
            owner=owner,
            public_id="PSM-CTL-0001",
            entity_type="INDIVIDUAL",
            business_name="Control Co",
            status="ACTIVE",
        )

    def test_suspend_and_reactivate_merchant(self, client, admin_user, user_model):
        merchant = self._merchant(user_model)
        client.force_login(admin_user)
        response = client.post(f"/administration/merchants/{merchant.public_id}/", {"action": "suspend"})
        assert response.status_code == 302
        merchant.refresh_from_db()
        assert merchant.status == "SUSPENDED"
        assert merchant.commercial_status == "SUSPENDED"

        response = client.post(f"/administration/merchants/{merchant.public_id}/", {"action": "reactivate"})
        assert response.status_code == 302
        merchant.refresh_from_db()
        assert merchant.status == "ACTIVE"
        assert merchant.commercial_status == "ACTIVE"
        assert AuditEvent.objects.filter(
            action="merchant.reactivate", resource_id=merchant.public_id
        ).exists()

    def test_assign_merchant_to_employee(self, client, admin_user, kyc_user, user_model):
        merchant = self._merchant(user_model, "assign@payswap.test")
        client.force_login(admin_user)
        response = client.post(
            f"/administration/merchants/{merchant.public_id}/",
            {"action": "assign", "assigned_to": str(kyc_user.pk)},
        )
        assert response.status_code == 302
        merchant.refresh_from_db()
        assert merchant.assigned_to_id == kyc_user.pk
        assert AuditEvent.objects.filter(action="merchant.assign", resource_id=merchant.public_id).exists()

    def test_grant_and_revoke_role(self, client, admin_user, kyc_user):
        client.force_login(admin_user)
        response = client.post(
            f"/administration/employees/{kyc_user.pk}/role/",
            {"action": "grant", "role": "operations"},
        )
        assert response.status_code == 302
        assert kyc_user.user_roles.filter(role__slug="operations").exists()
        assert AuditEvent.objects.filter(action="role.granted").exists()

        response = client.post(
            f"/administration/employees/{kyc_user.pk}/role/",
            {"action": "revoke", "role": "operations"},
        )
        assert response.status_code == 302
        assert not kyc_user.user_roles.filter(role__slug="operations").exists()
        assert AuditEvent.objects.filter(action="role.revoked").exists()

    def test_cannot_change_own_roles(self, client, admin_user):
        client.force_login(admin_user)
        client.post(
            f"/administration/employees/{admin_user.pk}/role/",
            {"action": "revoke", "role": "platform_admin"},
        )
        assert admin_user.user_roles.filter(role__slug="platform_admin").exists()

    def test_document_reject_with_reason(self, client, admin_user, merchant_user):
        merchant = Merchant.objects.create(
            owner=merchant_user,
            public_id="PSM-DOC-0001",
            entity_type="INDIVIDUAL",
            business_name="Doc Co",
        )
        from verification.models import Document

        document = Document.objects.create(
            merchant=merchant,
            public_id="DOC-P3-0001",
            doc_type=Document.DocType.PAN,
            uploaded_by=merchant_user,
        )
        client.force_login(admin_user)
        response = client.post(
            f"/administration/documents/{document.public_id}/",
            {"action": "reject", "reason": "Illegible scan"},
        )
        assert response.status_code == 302
        document.refresh_from_db()
        assert document.status == Document.Status.REJECTED


@pytest.mark.django_db
class TestMerchantProfileEdit:
    def test_merchant_updates_name_and_mobile(self, client, merchant_user):
        client.force_login(merchant_user)
        response = client.post(
            "/merchant/profile/",
            {"action": "profile", "name": "New Name", "mobile": "9876543210"},
        )
        assert response.status_code == 302
        merchant_user.refresh_from_db()
        assert merchant_user.name == "New Name"
        assert merchant_user.mobile == "9876543210"
        assert AuditEvent.objects.filter(action="profile.update", actor=merchant_user).exists()

    def test_merchant_rejects_bad_mobile(self, client, merchant_user):
        client.force_login(merchant_user)
        response = client.post(
            "/merchant/profile/",
            {"action": "profile", "name": "Name", "mobile": "12345"},
        )
        assert response.status_code == 302
        merchant_user.refresh_from_db()
        assert merchant_user.mobile != "12345"

    def test_merchant_saves_notification_preferences(self, client, merchant_user):
        client.force_login(merchant_user)
        response = client.post(
            "/merchant/profile/",
            {"action": "preferences", "email_enabled": "on"},
        )
        assert response.status_code == 302
        merchant_user.refresh_from_db()
        assert merchant_user.notification_preference.email_enabled is True
        assert merchant_user.notification_preference.sms_enabled is False
        assert AuditEvent.objects.filter(action="notification.preferences", actor=merchant_user).exists()
