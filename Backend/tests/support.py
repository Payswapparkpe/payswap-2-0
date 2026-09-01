"""Test helpers for onboarding flows.

`complete_required_draft` lives here — not in `merchants.services` — because it
fabricates fixture KYC data. It must never be reachable from production code.
"""

from merchants.privacy import encrypt_step_data
from merchants.services import next_public_id
from merchants.states import REQUIRED_BEFORE_SUBMIT, StepStatus
from verification.models import Document


def complete_required_draft(application) -> None:
    """Complete every required step with fixture data and attach a verified
    PAN document so the application satisfies the approval evidence gates."""
    for step in application.steps.filter(key__in=REQUIRED_BEFORE_SUBMIT):
        if step.key == "business":
            data = dict(step.data or {})
            if not data.get("legal_name"):
                data.update(
                    {
                        "legal_name": application.merchant.business_name or "Test Private Limited",
                        "cin": data.get("cin") or "U74999MH2018PTC123456",
                        "pan": data.get("pan") or "ABCDE1234F",
                        "gstin": data.get("gstin") or "27ABCDE1234F1Z5",
                    }
                )
            data.setdefault("registered_office", "12 MG Road, Mumbai, Maharashtra 400001")
            step.data = encrypt_step_data(data)
            application.merchant.business_name = data.get("legal_name") or application.merchant.business_name
            application.merchant.save(update_fields=["business_name"])
        elif step.key == "owners":
            data = dict(step.data or {})
            data.setdefault("owner_name", application.merchant.owner.name or "Test Signatory")
            data.setdefault("authorized_signatory", data["owner_name"])
            data.setdefault("designation", "Director")
            data.setdefault("ownership_percent", "100")
            step.data = encrypt_step_data(data)
        step.status = StepStatus.COMPLETE
        step.save(update_fields=["status", "data"])
    pans = application.merchant.documents.filter(doc_type=Document.DocType.PAN)
    if pans.exists():
        pans.update(status=Document.Status.VERIFIED)
    else:
        Document.objects.create(
            merchant=application.merchant,
            public_id=next_public_id("DOC", Document),
            doc_type=Document.DocType.PAN,
            status=Document.Status.VERIFIED,
            uploaded_by=application.merchant.owner,
        )
