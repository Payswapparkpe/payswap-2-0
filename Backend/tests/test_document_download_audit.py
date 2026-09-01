import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from audit.models import AuditEvent
from merchants.services import MerchantOnboardingService
from verification.models import Document
from verification.services import DocumentReviewService


@pytest.mark.django_db
class TestDocumentDownloadAudit:
    def test_owner_post_download_is_audited(self, client, merchant_user):
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        document = DocumentReviewService.register_upload(
            merchant=application.merchant,
            actor=merchant_user,
            doc_type=Document.DocType.PAN,
            uploaded_file=SimpleUploadedFile("pan.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        )
        client.force_login(merchant_user)
        response = client.post(f"/merchant/documents/{document.public_id}/download/")
        assert response.status_code == 200
        assert AuditEvent.objects.filter(
            action="verification.document_download",
            resource_id=document.public_id,
            actor=merchant_user,
        ).exists()
