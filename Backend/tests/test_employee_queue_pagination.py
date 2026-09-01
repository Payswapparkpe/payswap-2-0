import pytest


@pytest.mark.django_db
class TestEmployeeQueuePagination:
    def test_queue_pages_in_batches_of_fifty(self, client, kyc_user):
        client.force_login(kyc_user)
        response = client.get("/employee/queue/")
        assert response.status_code == 200
        page = response.context["page"]
        assert page.paginator.per_page == 50
