"""Match uploaded document identifiers against the merchant profile."""

from __future__ import annotations

from difflib import SequenceMatcher

from django.core.exceptions import ValidationError

from merchants.privacy import decrypt_step_data
from verification.names import match_names

MATCH_THRESHOLD = 70

DOC_PROFILE_KEYS = {
    "PAN": ("pan",),
    "GST": ("gstin",),
    "COI": ("cin", "llpin"),
    "AADHAAR": ("aadhaar",),
    "BANK_PROOF": ("account_last4", "account_number"),
}


def normalize_identifier(value: str) -> str:
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def score_identifiers(left: str, right: str) -> int:
    first = normalize_identifier(left)
    second = normalize_identifier(right)
    if not first or not second:
        return 0
    if first == second:
        return 100
    return round(SequenceMatcher(None, first, second).ratio() * 100)


def profile_identifiers(merchant) -> dict:
    application = merchant.applications.order_by("-created_at").first()
    business = {}
    owners = {}
    bank = {}
    if application:
        business_step = application.steps.filter(key="business").first()
        owners_step = application.steps.filter(key="owners").first()
        bank_step = application.steps.filter(key="bank").first()
        business = decrypt_step_data(business_step.data if business_step else {})
        owners = decrypt_step_data(owners_step.data if owners_step else {})
        bank = decrypt_step_data(bank_step.data if bank_step else {})
    return {
        "legal_name": business.get("legal_name") or merchant.business_name or "",
        "pan": business.get("pan", ""),
        "gstin": business.get("gstin", ""),
        "cin": business.get("cin", ""),
        "llpin": business.get("llpin", ""),
        "registered_office": business.get("registered_office", ""),
        "pincode": business.get("pincode", ""),
        "owner_name": owners.get("owner_name") or merchant.owner.name,
        "owner_dob": owners.get("owner_dob", ""),
        "aadhaar": owners.get("aadhaar", ""),
        "account_number": bank.get("account_number", ""),
        "account_last4": bank.get("account_last4", ""),
        "account_holder": bank.get("account_holder", ""),
        "ifsc": bank.get("ifsc", ""),
        "entity_type": merchant.entity_type,
    }


def expected_identifier(profile: dict, doc_type: str) -> str:
    for key in DOC_PROFILE_KEYS.get(doc_type, ()):
        value = (profile.get(key) or "").strip()
        if value:
            return value
    return ""


def match_document(*, merchant, doc_type: str, document_number: str = "", holder_name: str = "") -> dict:
    profile = profile_identifiers(merchant)
    expected = expected_identifier(profile, doc_type)
    if doc_type == "BANK_PROOF":
        submitted = normalize_identifier(document_number)
        last4 = normalize_identifier(profile.get("account_last4") or profile.get("account_number") or "")[-4:]
        if submitted and last4 and submitted.endswith(last4):
            number_score = 100
        else:
            number_score = score_identifiers(document_number, expected)
    else:
        number_score = score_identifiers(document_number, expected)
    profile_name = profile.get("legal_name") or profile.get("owner_name") or ""
    if holder_name.strip() and profile_name:
        _category, name_ratio = match_names(holder_name, profile_name)
        name_score = round(name_ratio * 100)
        score = round(number_score * 0.7 + name_score * 0.3)
    else:
        score = number_score
    return {
        "doc_type": doc_type,
        "expected": expected,
        "score": score,
        "ok": score >= MATCH_THRESHOLD,
        "threshold": MATCH_THRESHOLD,
        "profile": profile,
    }


def assert_document_matches_profile(
    *, merchant, doc_type: str, document_number: str = "", holder_name: str = ""
) -> dict:
    if doc_type not in DOC_PROFILE_KEYS:
        return {"score": 100, "ok": True, "threshold": MATCH_THRESHOLD, "expected": ""}
    result = match_document(
        merchant=merchant,
        doc_type=doc_type,
        document_number=document_number,
        holder_name=holder_name,
    )
    label = {
        "PAN": "PAN",
        "GST": "GSTIN",
        "COI": "CIN or LLPIN",
        "AADHAAR": "Aadhaar",
        "BANK_PROOF": "bank account number",
    }[doc_type]
    if not result["expected"]:
        raise ValidationError(
            f"Add the {label} and date of birth on your profile before uploading this document."
        )
    if not normalize_identifier(document_number):
        raise ValidationError("Enter a valid document number.")
    if not result["ok"]:
        raise ValidationError(
            f"This document matches your profile at {result['score']}%. "
            f"At least {MATCH_THRESHOLD}% match is required."
        )
    return result


def annotate_documents(merchant, documents) -> list:
    rows = []
    for document in documents:
        number = document.get_document_number()
        match = None
        if document.doc_type in DOC_PROFILE_KEYS:
            match = match_document(merchant=merchant, doc_type=document.doc_type, document_number=number)
        rows.append({"document": document, "match": match, "number": number})
    return rows


def profile_gaps(merchant) -> list[str]:
    profile = profile_identifiers(merchant)
    gaps = []
    if not (profile.get("legal_name") or "").strip():
        gaps.append("legal name")
    if not (profile.get("pan") or "").strip():
        gaps.append("PAN")
    if not (profile.get("owner_dob") or "").strip():
        gaps.append("date of birth")
    return gaps
