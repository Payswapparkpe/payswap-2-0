import pytest

from merchants.services import MerchantOnboardingService
from portals.search import search


@pytest.mark.django_db
class TestSearchPermissions:
    def test_merchant_search_does_not_return_other_merchant(self, merchant_user, other_merchant_user):
        own = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        other = MerchantOnboardingService.start(other_merchant_user, entity_type="PRIVATE_LIMITED")
        results = search(merchant_user, other.public_id)
        labels = " ".join(item["label"] for item in results)
        assert other.public_id not in labels
        own_results = search(merchant_user, own.public_id)
        assert own_results == [] or own.public_id in " ".join(item["label"] for item in own_results)

    def test_admin_can_find_merchant(self, admin_user, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        results = search(admin_user, application.merchant.public_id)
        assert any(application.merchant.public_id in item["label"] for item in results)
