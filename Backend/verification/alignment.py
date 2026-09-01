"""Cross-document name alignment for KYC / KYB.

Individual entities: PAN, Aadhaar (DigiLocker), and bank account names must align.
Business entities: the legal name from company PAN / GSTIN must match the bank name.
"""

from __future__ import annotations

from merchants.models import Merchant
from merchants.privacy import decrypt_step_data
from verification.models import VerificationRecord
from verification.names import CATEGORY_EXACT, CATEGORY_STRONG, match_names

_ACCEPTABLE = {CATEGORY_EXACT, CATEGORY_STRONG}


def _latest_verified_name(merchant, vtype: str) -> str:
    record = (
        merchant.verification_records.filter(
            verification_type=vtype,
            status__in={
                VerificationRecord.Status.VERIFIED,
                VerificationRecord.Status.PARTIALLY_VERIFIED,
            },
        )
        .order_by("-completed_at")
        .first()
    )
    if record and record.verified_name:
        return record.verified_name.strip()
    return ""


def _application_names(application) -> dict:
    business = {}
    owners = {}
    identity = {}
    signatory = {}
    if application:
        for key, target in (
            ("business", business),
            ("owners", owners),
            ("identity", identity),
            ("signatory", signatory),
        ):
            step = application.steps.filter(key=key).first()
            if step:
                target.update(decrypt_step_data(step.data))
    return {
        "business": business,
        "owners": owners,
        "identity": identity,
        "signatory": signatory,
    }


def expected_bank_holder_name(*, merchant: Merchant, application=None) -> str:
    """Name the bank account should be registered under for this entity."""
    entity_type = merchant.entity_type or Merchant.EntityType.INDIVIDUAL
    individual_like = entity_type in {
        Merchant.EntityType.INDIVIDUAL,
        Merchant.EntityType.PROPRIETORSHIP,
    }
    ctx = _application_names(application)
    if individual_like:
        for source in (
            _latest_verified_name(merchant, VerificationRecord.Type.AADHAAR),
            _latest_verified_name(merchant, VerificationRecord.Type.PAN),
            ctx["signatory"].get("name") or "",
            ctx["owners"].get("owner_name") or "",
            merchant.business_name or "",
        ):
            if source.strip():
                return source.strip()
        return ""
    for source in (
        _latest_verified_name(merchant, VerificationRecord.Type.GSTIN),
        _latest_verified_name(merchant, VerificationRecord.Type.PAN),
        ctx["business"].get("legal_name") or "",
        merchant.business_name or "",
    ):
        if isinstance(source, str) and source.strip():
            return source.strip()
    return ""


def evaluate_alignment(*, merchant: Merchant, application=None) -> dict:
    """Return structured alignment checks for API / onboarding gates."""
    entity_type = merchant.entity_type or Merchant.EntityType.INDIVIDUAL
    individual_like = entity_type in {
        Merchant.EntityType.INDIVIDUAL,
        Merchant.EntityType.PROPRIETORSHIP,
    }
    expected_bank = expected_bank_holder_name(merchant=merchant, application=application)
    checks: list[dict] = []
    issues: list[str] = []

    pan_name = _latest_verified_name(merchant, VerificationRecord.Type.PAN)
    aadhaar_name = _latest_verified_name(merchant, VerificationRecord.Type.AADHAAR)
    bank_record = (
        merchant.verification_records.filter(verification_type=VerificationRecord.Type.BANK_ACCOUNT)
        .order_by("-completed_at")
        .first()
    )
    bank_name = ""
    if bank_record:
        bank_name = (bank_record.verified_name or "").strip()
        if not bank_name:
            bank_name = (bank_record.get_provider_response().get("name_at_bank") or "").strip()

    def add_check(kind: str, left: str, right: str):
        if not left.strip() or not right.strip():
            return
        category, score = match_names(left, right)
        ok = category in _ACCEPTABLE
        checks.append(
            {
                "kind": kind,
                "left": left,
                "right": right,
                "category": category,
                "score": score,
                "ok": ok,
            }
        )
        if not ok:
            issues.append(f"{kind}: names do not match closely enough.")

    if individual_like:
        add_check("pan_aadhaar", pan_name, aadhaar_name)
        add_check("pan_bank", pan_name or aadhaar_name, bank_name)
        add_check("aadhaar_bank", aadhaar_name, bank_name)
    else:
        reference = expected_bank or pan_name
        add_check("entity_bank", reference, bank_name)

    if expected_bank and bank_name:
        add_check("expected_bank", expected_bank, bank_name)

    return {
        "ok": not issues,
        "entityType": entity_type,
        "expectedBankName": expected_bank,
        "checks": checks,
        "issues": issues,
        "names": {
            "pan": pan_name,
            "aadhaar": aadhaar_name,
            "bank": bank_name,
        },
    }
