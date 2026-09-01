"""Regression: merchant downloading their own agreement must not 500.

The view compared ``agreement.merchant.user_id`` — a field that does not exist
(``Merchant.owner`` is the OneToOneField) — so every merchant-side download
raised AttributeError. Staff access short-circuited before the bug, which is
why only the merchant path was broken.
"""

import pytest
from django.core.files.base import ContentFile

from agreements.models import Agreement
from merchants.models import Merchant
from merchants.services import MerchantOnboardingService


def _agreement(merchant_user, public_id="AGR-TESTDL"):
    application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
    agreement = Agreement.objects.create(
        merchant=application.merchant,
        public_id=public_id,
        body="placeholder",
    )
    agreement.document_file.save("source.pdf", ContentFile(b"%PDF-1.4 test"), save=True)
    return agreement


@pytest.mark.django_db
class TestAgreementDownloadAccess:
    def test_merchant_downloads_own_agreement(self, client, merchant_user):
        agreement = _agreement(merchant_user)
        client.force_login(merchant_user)
        response = client.post(f"/merchant/agreements/{agreement.public_id}/download/", {"kind": "source"})
        assert response.status_code == 200
        assert b"%PDF" in b"".join(response.streaming_content)

    def test_other_merchant_is_denied(self, client, merchant_user, other_merchant_user):
        agreement = _agreement(merchant_user)
        Merchant.objects.create(
            owner=other_merchant_user,
            public_id="PSM-009998",
            business_name="Other",
            status="ACTIVE",
        )
        client.force_login(other_merchant_user)
        response = client.post(f"/merchant/agreements/{agreement.public_id}/download/", {"kind": "source"})
        assert response.status_code == 403

    def test_get_is_not_allowed(self, client, merchant_user):
        agreement = _agreement(merchant_user)
        client.force_login(merchant_user)
        response = client.get(f"/merchant/agreements/{agreement.public_id}/download/")
        assert response.status_code == 405
