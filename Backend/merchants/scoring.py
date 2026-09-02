"""Risk scoring and entered-vs-registry comparison for merchant review."""

from __future__ import annotations

from merchants.matching import profile_identifiers, score_identifiers
from merchants.models import Merchant
from merchants.privacy import decrypt_step_data
from verification.alignment import evaluate_alignment
from verification.models import VerificationRecord
from verification.names import (
    CATEGORY_EXACT,
    CATEGORY_PARTIAL,
    CATEGORY_STRONG,
    CATEGORY_WEAK,
    match_names,
)

_MATCH = "match"
_PARTIAL = "partial"
_MISMATCH = "mismatch"
_UNVERIFIED = "unverified"

_INDIVIDUAL_LIKE = {
    Merchant.EntityType.INDIVIDUAL,
    Merchant.EntityType.PROPRIETORSHIP,
}


def _name_status(category: str, score: float) -> str:
    if category in {CATEGORY_EXACT, CATEGORY_STRONG}:
        return _MATCH
    if category == CATEGORY_PARTIAL:
        return _PARTIAL
    if category in {CATEGORY_WEAK} or score > 0:
        return _MISMATCH
    return _UNVERIFIED


def _identifier_status(score: int) -> str:
    if score >= 100:
        return _MATCH
    if score >= 70:
        return _PARTIAL
    if score > 0:
        return _MISMATCH
    return _UNVERIFIED


def _add_row(
    rows: list[dict],
    *,
    check: str,
    field: str,
    entered: str,
    registry: str,
    score: int | float,
    status: str,
    domain: str,
    record_id: str = "",
) -> None:
    entered_text = (entered or "").strip()
    registry_text = (registry or "").strip()
    if not entered_text and not registry_text:
        return
    rows.append(
        {
            "check": check,
            "field": field,
            "entered": entered_text or "—",
            "registry": registry_text or "—",
            "score": score,
            "status": status if (entered_text and registry_text) else _UNVERIFIED,
            "domain": domain,
            "record_id": record_id,
        }
    )


def _step_data(application) -> tuple[dict, dict, dict]:
    business, owners, bank = {}, {}, {}
    if application is None:
        return business, owners, bank
    for step in application.steps.all():
        plain = decrypt_step_data(step.data)
        if step.key == "business":
            business = plain
        elif step.key == "owners":
            owners = plain
        elif step.key == "bank":
            bank = plain
    return business, owners, bank


def _person_pan_dob(owners: dict, business: dict) -> tuple[str, str, str]:
    owner_kyc = owners.get("owner_kyc") or {}
    signatory_kyc = business.get("signatory_kyc") or {}
    name = (
        owners.get("owner_name")
        or owner_kyc.get("name")
        or signatory_kyc.get("name")
        or ""
    )
    pan = owner_kyc.get("pan") or signatory_kyc.get("pan") or ""
    dob = owner_kyc.get("dob") or signatory_kyc.get("dob") or owners.get("owner_dob") or ""
    return name, pan, dob


def _provider_value(provider: dict, *keys: str) -> str:
    for key in keys:
        value = provider.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def build_match_rows(*, merchant, application, records) -> list[dict]:
    """Compare merchant-entered data against verified registry/API values."""
    business, owners, bank = _step_data(application)
    profile = profile_identifiers(merchant)
    entity_type = merchant.entity_type or Merchant.EntityType.INDIVIDUAL
    individual = entity_type in _INDIVIDUAL_LIKE
    rows: list[dict] = []

    person_name, person_pan, person_dob = _person_pan_dob(owners, business)
    legal_name = (profile.get("legal_name") or business.get("legal_name") or "").strip()
    if individual and not legal_name:
        legal_name = person_name

    for record in records:
        if record.status not in {
            VerificationRecord.Status.VERIFIED,
            VerificationRecord.Status.PARTIALLY_VERIFIED,
        }:
            continue
        provider = record.get_provider_response()
        record_id = record.public_id
        vtype = record.verification_type

        if vtype == VerificationRecord.Type.PAN:
            entered_pan = (profile.get("pan") or business.get("pan") or person_pan or "").strip()
            registry_pan = record.get_document() or _provider_value(provider, "pan")
            pan_score = score_identifiers(entered_pan, registry_pan)
            _add_row(
                rows,
                check="PAN",
                field="PAN number",
                entered=entered_pan,
                registry=registry_pan,
                score=pan_score,
                status=_identifier_status(pan_score),
                domain="kyc" if individual else "kyb",
                record_id=record_id,
            )
            registry_name = record.verified_name or _provider_value(
                provider, "registered_name", "name_pan_card", "name"
            )
            entered_name = person_name if individual else legal_name
            category, ratio = match_names(entered_name, registry_name)
            _add_row(
                rows,
                check="PAN",
                field="Registered name",
                entered=entered_name,
                registry=registry_name,
                score=round(ratio * 100),
                status=_name_status(category, ratio),
                domain="kyc" if individual else "kyb",
                record_id=record_id,
            )

        elif vtype in {VerificationRecord.Type.AADHAAR, VerificationRecord.Type.DIGILOCKER}:
            entered_name = person_name or owners.get("owner_name") or ""
            registry_name = record.verified_name or _provider_value(
                provider, "name", "full_name"
            )
            category, ratio = match_names(entered_name, registry_name)
            _add_row(
                rows,
                check="DigiLocker",
                field="Person name",
                entered=entered_name,
                registry=registry_name,
                score=round(ratio * 100),
                status=_name_status(category, ratio),
                domain="kyc",
                record_id=record_id,
            )
            entered_dob = person_dob
            registry_dob = record.verified_dob or _provider_value(provider, "dob", "date_of_birth")
            dob_score = score_identifiers(entered_dob, registry_dob)
            _add_row(
                rows,
                check="DigiLocker",
                field="Date of birth",
                entered=entered_dob,
                registry=registry_dob,
                score=dob_score,
                status=_identifier_status(dob_score),
                domain="kyc",
                record_id=record_id,
            )

        elif vtype == VerificationRecord.Type.GSTIN:
            entered_gstin = (business.get("gstin") or "").strip()
            registry_gstin = record.get_document() or _provider_value(provider, "gstin")
            gst_score = score_identifiers(entered_gstin, registry_gstin)
            _add_row(
                rows,
                check="GSTIN",
                field="GSTIN",
                entered=entered_gstin,
                registry=registry_gstin,
                score=gst_score,
                status=_identifier_status(gst_score),
                domain="kyb",
                record_id=record_id,
            )
            registry_name = _provider_value(
                provider, "legal_name_of_business", "trade_name_of_business", "registered_name"
            ) or (record.verified_name or "")
            category, ratio = match_names(legal_name, registry_name)
            _add_row(
                rows,
                check="GSTIN",
                field="Legal name",
                entered=legal_name,
                registry=registry_name,
                score=round(ratio * 100),
                status=_name_status(category, ratio),
                domain="kyb",
                record_id=record_id,
            )
            entered_address = (business.get("registered_office") or "").strip()
            registry_address = _provider_value(provider, "principal_place_address", "registered_address")
            if not registry_address:
                registry_address = ", ".join(
                    p
                    for p in (
                        record.verified_address,
                        record.verified_city,
                        record.verified_state,
                        record.verified_pincode,
                    )
                    if p
                )
            if entered_address or registry_address:
                category, ratio = match_names(entered_address, registry_address)
                _add_row(
                    rows,
                    check="GSTIN",
                    field="Principal address",
                    entered=entered_address,
                    registry=registry_address,
                    score=round(ratio * 100),
                    status=_name_status(category, ratio),
                    domain="kyb",
                    record_id=record_id,
                )

        elif vtype == VerificationRecord.Type.CIN:
            entered_cin = (business.get("cin") or "").strip()
            registry_cin = record.get_document() or _provider_value(provider, "cin")
            cin_score = score_identifiers(entered_cin, registry_cin)
            _add_row(
                rows,
                check="CIN",
                field="CIN",
                entered=entered_cin,
                registry=registry_cin,
                score=cin_score,
                status=_identifier_status(cin_score),
                domain="kyb",
                record_id=record_id,
            )
            registry_name = _provider_value(provider, "company_name") or (record.verified_name or "")
            category, ratio = match_names(legal_name, registry_name)
            _add_row(
                rows,
                check="CIN",
                field="Company name",
                entered=legal_name,
                registry=registry_name,
                score=round(ratio * 100),
                status=_name_status(category, ratio),
                domain="kyb",
                record_id=record_id,
            )

        elif vtype == VerificationRecord.Type.UDYAM:
            entered_udyam = (business.get("udyam_number") or "").strip()
            registry_udyam = record.get_document() or _provider_value(provider, "udyam_number", "udyam")
            udyam_score = score_identifiers(entered_udyam, registry_udyam)
            _add_row(
                rows,
                check="Udyam",
                field="Udyam number",
                entered=entered_udyam,
                registry=registry_udyam,
                score=udyam_score,
                status=_identifier_status(udyam_score),
                domain="kyb" if not individual else "kyc",
                record_id=record_id,
            )
            registry_name = _provider_value(provider, "enterprise_name") or (
                business.get("udyam_enterprise_name") or ""
            )
            category, ratio = match_names(legal_name, registry_name)
            _add_row(
                rows,
                check="Udyam",
                field="Enterprise name",
                entered=legal_name,
                registry=registry_name,
                score=round(ratio * 100),
                status=_name_status(category, ratio),
                domain="kyb" if not individual else "kyc",
                record_id=record_id,
            )
            owner_name = _provider_value(provider, "owner_name") or (record.verified_name or "")
            category, ratio = match_names(person_name or legal_name, owner_name)
            _add_row(
                rows,
                check="Udyam",
                field="Owner name",
                entered=person_name or legal_name,
                registry=owner_name,
                score=round(ratio * 100),
                status=_name_status(category, ratio),
                domain="kyc",
                record_id=record_id,
            )

        elif vtype == VerificationRecord.Type.BANK_ACCOUNT:
            entered_holder = (bank.get("account_holder") or "").strip()
            registry_holder = _provider_value(provider, "name_at_bank") or (record.verified_name or "")
            if record.name_match_score is not None:
                score = round(float(record.name_match_score) * 100)
                status = _MATCH if score >= 80 else _PARTIAL if score >= 50 else _MISMATCH
            else:
                category, ratio = match_names(entered_holder, registry_holder)
                score = round(ratio * 100)
                status = _name_status(category, ratio)
            _add_row(
                rows,
                check="Bank",
                field="Account holder",
                entered=entered_holder,
                registry=registry_holder,
                score=score,
                status=status,
                domain="kyc" if individual else "kyb",
                record_id=record_id,
            )

    alignment = evaluate_alignment(merchant=merchant, application=application)
    for check in alignment.get("checks") or []:
        _add_row(
            rows,
            check=check.get("kind", "alignment").replace("_", " ").title(),
            field="Cross-check",
            entered=check.get("left", ""),
            registry=check.get("right", ""),
            score=round(float(check.get("score") or 0) * 100),
            status=_MATCH if check.get("ok") else _MISMATCH,
            domain="kyc" if individual else "kyb",
        )

    return rows


def _score_domain(rows: list[dict], domain: str) -> dict:
    scoped = [row for row in rows if row.get("domain") == domain]
    if not scoped:
        return {
            "score": 0,
            "band": "High",
            "matched": 0,
            "partial": 0,
            "mismatches": 0,
            "total": 0,
        }
    matched = sum(1 for row in scoped if row["status"] == _MATCH)
    partial = sum(1 for row in scoped if row["status"] == _PARTIAL)
    mismatches = sum(1 for row in scoped if row["status"] == _MISMATCH)
    total = len(scoped)
    weighted = matched + partial * 0.5
    score = round(weighted / total * 100) if total else 0
    band = band_from_score(score)
    return {
        "score": score,
        "band": band,
        "matched": matched,
        "partial": partial,
        "mismatches": mismatches,
        "total": total,
    }


def band_from_score(score: int) -> str:
    if score >= 80:
        return "Low"
    if score >= 50:
        return "Medium"
    return "High"


def risk_status_from_score(score: int) -> str:
    if score >= 80:
        return Merchant.RiskStatus.CLEAR
    if score >= 50:
        return Merchant.RiskStatus.REVIEW
    return Merchant.RiskStatus.HIGH


def compute_review_scores(*, merchant, application, records) -> dict:
    """Full scoring package for admin/employee review templates."""
    match_rows = build_match_rows(merchant=merchant, application=application, records=records)
    kyc = _score_domain(match_rows, "kyc")
    kyb = _score_domain(match_rows, "kyb")
    entity_type = merchant.entity_type or Merchant.EntityType.INDIVIDUAL
    individual = entity_type in _INDIVIDUAL_LIKE
    if individual and kyb["total"] == 0:
        overall_score = kyc["score"]
    elif not individual and kyc["total"] == 0:
        overall_score = kyb["score"]
    else:
        overall_score = round((kyc["score"] + kyb["score"]) / 2)
    overall_band = band_from_score(overall_score)
    mismatch_count = sum(1 for row in match_rows if row["status"] == _MISMATCH)
    return {
        "match_rows": match_rows,
        "kyc": kyc,
        "kyb": kyb,
        "overall_score": overall_score,
        "overall_band": overall_band,
        "mismatch_count": mismatch_count,
        "risk_status": risk_status_from_score(overall_score),
    }


def update_merchant_risk_status(merchant, *, application=None) -> str:
    """Recompute and persist merchant.risk_status from latest verification data."""
    records = list(
        merchant.verification_records.order_by("-completed_at", "-requested_at")[:50]
    )
    if application is None:
        application = merchant.applications.order_by("-created_at").first()
    scores = compute_review_scores(merchant=merchant, application=application, records=records)
    new_status = scores["risk_status"]
    if merchant.risk_status != new_status:
        merchant.risk_status = new_status
        merchant.save(update_fields=["risk_status"])
    return new_status
