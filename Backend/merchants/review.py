"""Reviewer-facing view of a submitted onboarding application.

Both the administration merchant detail page and the employee KYC queue render
the same application, so the sections are built once here. By default values
are masked via :func:`display_step_data`; pass ``unmasked=True`` for staff with
``merchant.manage`` so reviewers see full identifiers and provider payloads.
"""

import json

from django.conf import settings

from core.crypto import decrypt_text

from .models import Merchant
from .privacy import MASK_BULLET, decrypt_step_data, display_step_data

# Keys commonly present in Cashfree / DigiLocker provider payloads.
_PROVIDER_SENSITIVE_KEYS = frozenset(
    {
        "pan",
        "gstin",
        "cin",
        "llpin",
        "aadhaar",
        "uid",
        "eaadhaar",
        "account_number",
        "bank_account",
        "mobile",
        "phone",
        "email",
        "document_number",
        "client_secret",
        "secret",
        "token",
        "authorization",
    }
)

_STEP_TITLES = {
    "business": "Business & KYB",
    "owners": "People & ownership",
    "bank": "Bank account",
    "documents": "Documents acknowledgement",
    "review": "Review & compliance",
}

_PROVIDER_FIELD_LABELS = {
    "pan_status": "PAN status",
    "name_match": "Name match",
    "aadhaar_seeding_status": "Aadhaar seeding",
    "registered_name": "Registered name",
    "gst_in_status": "GSTIN status",
    "legal_name_of_business": "Legal name",
    "trade_name_of_business": "Trade name",
    "constitution_of_business": "Constitution",
    "taxpayer_type": "Taxpayer type",
    "date_of_registration": "GST registration date",
    "principal_place_address": "Principal place",
    "account_status": "Account status",
    "name_at_bank": "Name at bank",
    "bank_name": "Bank",
    "branch": "Branch",
    "ifsc": "IFSC",
    "utr": "UTR reference",
    "company_name": "Company name",
    "company_status": "Company status",
    "date_of_incorporation": "Date of incorporation",
    "registered_address": "Registered address",
    "enterprise_name": "Enterprise name",
    "udyam_number": "Udyam number",
    "owner_name": "Owner name",
    "status": "Provider status",
    "valid": "Valid",
}

_TYPE_PROVIDER_FIELDS: dict[str, tuple[str, ...]] = {
    "PAN": ("pan_status", "name_match", "aadhaar_seeding_status", "registered_name", "status"),
    "GSTIN": (
        "gst_in_status",
        "legal_name_of_business",
        "trade_name_of_business",
        "constitution_of_business",
        "taxpayer_type",
        "date_of_registration",
        "principal_place_address",
    ),
    "BANK_ACCOUNT": ("account_status", "name_at_bank", "bank_name", "branch", "ifsc", "utr"),
    "IFSC": ("bank", "branch", "address", "city", "state", "neft", "imps"),
    "CIN": ("company_name", "company_status", "date_of_incorporation", "registered_address"),
    "UDYAM": ("enterprise_name", "udyam_number", "owner_name", "status"),
    "DIGILOCKER": ("status", "sub_status"),
}

#: Sections a reviewer can send back for correction. Admin and employee portals
#: must offer the same list, otherwise a send-back means different things.
CLARIFICATION_SECTIONS = [
    ("business", "Business details"),
    ("owners", "People and ownership"),
    ("bank", "Bank account"),
    ("documents", "Documents"),
]


def _row(label: str, value, *, hint: str = "") -> dict:
    if isinstance(value, bool):
        value = "Yes" if value else "No"
    text = "" if value is None else str(value).strip()
    return {"label": label, "value": text or "—", "hint": hint, "missing": not text}


def _person(label: str, stored: dict | None, *, fallback_name: str = "") -> dict | None:
    stored = stored or {}
    name = stored.get("name") or fallback_name
    if not name and not stored.get("pan"):
        return None
    address = stored.get("address") or {}
    location = ", ".join(
        part for part in (address.get("city"), address.get("state"), address.get("pin")) if part
    )
    return {
        "role": label,
        "name": name or "—",
        "verified": bool(stored.get("verified")),
        "rows": [
            _row("PAN", stored.get("pan")),
            _row("Date of birth", stored.get("dob")),
            _row("Mobile", stored.get("mobile")),
            _row("KYC route", (stored.get("path") or "").replace("_", " ").title()),
            _row("Address", ", ".join(p for p in (address.get("line1"), location) if p)),
        ],
    }


def _people_sections(business: dict, owners: dict) -> list[dict]:
    people = []
    for label, stored, fallback in (
        ("Account opener / signatory", business.get("signatory_kyc"), owners.get("owner_name")),
        ("Business owner / director", owners.get("owner_kyc"), ""),
        ("Authorised signatory", owners.get("auth_signatory_kyc"), owners.get("authorized_signatory")),
    ):
        entry = _person(label, stored, fallback_name=fallback or "")
        if entry:
            people.append(entry)
    return people


def _registry_rows(entries, *, party_id: str, title: str, empty: str) -> dict:
    rows = []
    for item in entries or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "name": item.get("name") or "—",
                "designation": item.get("designation") or item.get("relationship") or "—",
                "identifier": item.get("din") or item.get("pan") or "—",
                "ownership": item.get("ownershipPercent") or item.get("ownership_percent") or "",
                "verified": bool(item.get("kycVerified") or item.get("kyc_verified")),
            }
        )
    return {"id": party_id, "title": title, "rows": rows, "empty": empty}


def _step_payloads(application, *, unmasked: bool) -> dict:
    transform = decrypt_step_data if unmasked else display_step_data
    return {step.key: transform(step.data) for step in application.steps.all()}


def _individual_identity_enrichment(business: dict, owners: dict) -> tuple[dict, dict]:
    """Pull DigiLocker PAN/DOB from owner KYC when the business step has none."""
    owner_kyc = owners.get("owner_kyc") or {}
    signatory_kyc = business.get("signatory_kyc") or {}
    enriched = dict(business)
    owners_out = dict(owners)
    if not (enriched.get("pan") or "").strip():
        enriched["pan"] = owner_kyc.get("pan") or signatory_kyc.get("pan") or ""
    if not (enriched.get("legal_name") or "").strip():
        enriched["legal_name"] = (
            owner_kyc.get("name")
            or signatory_kyc.get("name")
            or owners_out.get("owner_name")
            or ""
        )
    if not (owners_out.get("owner_dob") or "").strip():
        owners_out["owner_dob"] = owner_kyc.get("dob") or signatory_kyc.get("dob") or ""
    return enriched, owners_out


def application_review_context(application, *, unmasked: bool = False) -> dict:
    """Section-grouped application data for the review templates."""
    if application is None:
        return {"available": False, "sections": [], "people": [], "steps": {}, "unmasked": unmasked}

    steps = _step_payloads(application, unmasked=unmasked)
    business = steps.get("business") or {}
    owners = steps.get("owners") or {}
    bank = steps.get("bank") or {}
    review = steps.get("review") or {}
    compliance = review.get("compliance") or {}
    entity_type = application.merchant.entity_type

    if entity_type in {Merchant.EntityType.INDIVIDUAL, Merchant.EntityType.PROPRIETORSHIP}:
        business, owners = _individual_identity_enrichment(business, owners)
        steps = {**steps, "business": business, "owners": owners}

    identity_rows = [
        _row("PAN", business.get("pan")),
        _row("GSTIN", business.get("gstin"), hint="Merchant declared no GSTIN" if business.get("no_gstin") else ""),
    ]
    if entity_type in {Merchant.EntityType.PRIVATE_LIMITED, Merchant.EntityType.PUBLIC_LIMITED}:
        identity_rows.append(_row("CIN", business.get("cin")))
    if entity_type == Merchant.EntityType.LLP:
        identity_rows.append(_row("LLPIN", business.get("llpin")))
    if entity_type in {Merchant.EntityType.INDIVIDUAL, Merchant.EntityType.PROPRIETORSHIP}:
        identity_rows.append(_row("Udyam", business.get("udyam_number")))
        identity_rows.append(_row("Udyam enterprise", business.get("udyam_enterprise_name")))
    identity_rows.append(_row("Date of incorporation", business.get("doi")))

    sections = [
        {
            "id": "business",
            "title": "Business",
            "rows": [
                _row("Legal name", business.get("legal_name")),
                _row("Brand name", business.get("brand_name")),
                _row("Entity type", application.merchant.get_entity_type_display()),
                _row("Category", business.get("category")),
                _row("Sub-category", business.get("sub_category")),
                _row("Website", business.get("website")),
                _row("Expected monthly volume", business.get("monthly_volume")),
            ],
        },
        {"id": "identity", "title": "Registry identifiers", "rows": identity_rows},
        {
            "id": "addresses",
            "title": "Addresses",
            "rows": [
                _row("Registered office", business.get("registered_office")),
                _row("City", business.get("city")),
                _row("State", business.get("state")),
                _row("PIN", business.get("pincode")),
            ],
        },
        {
            "id": "bank",
            "title": "Bank account",
            "rows": [
                _row("Account holder", bank.get("account_holder")),
                _row("Account number", bank.get("account_number")),
                _row("IFSC", bank.get("ifsc")),
                _row("Account type", (bank.get("account_type") or "").title()),
                _row("Bank", bank.get("bank_name")),
                _row("Branch", bank.get("branch")),
                _row("Penny drop", (bank.get("penny_drop_status") or "idle").replace("_", " ").title()),
            ],
        },
        {
            "id": "compliance",
            "title": "Compliance declarations",
            "rows": [
                _row("Privacy policy published", compliance.get("privacyPolicy")),
                _row("Refund policy published", compliance.get("refundPolicy")),
                _row("Terms accepted", compliance.get("terms")),
                _row("Physical address confirmed", compliance.get("physicalAddress")),
                _row("Authorised to bind entity", compliance.get("authorisedDeclaration")),
                _row("Truth declaration", compliance.get("truthDeclaration") or review.get("confirmed")),
                _row("DPDP consent", compliance.get("dpdpConsent")),
            ],
        },
    ]

    # A reviewer's first question is "what is missing", so each section carries its
    # own filled/total count rather than making them scan every row for a dash.
    for section in sections:
        section["total"] = len(section["rows"])
        section["filled"] = sum(1 for row in section["rows"] if not row["missing"])
        if section["filled"] == section["total"]:
            section["state"] = "full"
        elif section["filled"] == 0:
            section["state"] = "empty"
        else:
            section["state"] = "partial"

    directors = _registry_rows(
        business.get("registry_directors"),
        party_id="directors",
        title="Directors (registry)",
        empty="No directors fetched from the registry.",
    )
    members = _registry_rows(
        business.get("registry_members"),
        party_id="members",
        title="Partners / trustees",
        empty="No partners or trustees recorded.",
    )
    ubos = _registry_rows(
        business.get("ubos"),
        party_id="ubos",
        title="Beneficial owners",
        empty="No beneficial owners declared.",
    )

    return {
        "available": True,
        "unmasked": unmasked,
        "sections": sections,
        "people": _people_sections(business, owners),
        "signatory_is_owner": business.get("signatory_is_owner"),
        "kyc_person_is_authorised_signatory": business.get("kyc_person_is_authorised_signatory"),
        "signatory_relation": owners.get("designation") or "",
        "directors": directors,
        "members": members,
        "ubos": ubos,
        # Same three dicts, as a list the template can loop over.
        "parties": [directors, members, ubos],
        "steps": steps,
    }


def _mask_provider_scalar(key: str, value) -> str:
    text = "" if value is None else str(value).strip()
    if not text or key not in _PROVIDER_SENSITIVE_KEYS:
        return text
    if len(text) <= 4:
        return MASK_BULLET * len(text)
    return MASK_BULLET * max(len(text) - 4, 0) + text[-4:]


def display_provider_payload(payload: dict | list | None):
    """Return a display-safe copy of a provider JSON payload."""
    if payload is None:
        return {}
    if isinstance(payload, list):
        return [display_provider_payload(item) for item in payload]
    if not isinstance(payload, dict):
        return payload
    masked: dict = {}
    for key, value in payload.items():
        lowered = key.lower()
        if isinstance(value, (dict, list)):
            masked[key] = display_provider_payload(value)
        elif lowered in _PROVIDER_SENSITIVE_KEYS:
            masked[key] = _mask_provider_scalar(lowered, value)
        else:
            masked[key] = value
    return masked


def format_review_json(payload) -> str:
    if not payload:
        return ""
    return json.dumps(payload, indent=2, sort_keys=True, default=str)


def _verification_verified_data(record, *, unmasked: bool = False) -> dict:
    raw = decrypt_text(record.verified_data_encrypted) if record.verified_data_encrypted else ""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed if unmasked else display_provider_payload(parsed)


def _provider_payload_rows(payload: dict | list | None, *, prefix: str = "") -> list[dict]:
    rows: list[dict] = []
    if payload is None:
        return rows
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            rows.extend(_provider_payload_rows(item, prefix=f"{prefix}[{index}]"))
        return rows
    if not isinstance(payload, dict):
        row = _furnish_row(prefix or "value", payload)
        return [row] if row else []
    for key, value in sorted(payload.items()):
        label = f"{prefix}.{key}" if prefix else key.replace("_", " ").title()
        if isinstance(value, (dict, list)):
            rows.extend(_provider_payload_rows(value, prefix=label))
        else:
            row = _furnish_row(label, value)
            if row:
                rows.append(row)
    return rows


def _furnish_row(label: str, value, *, hint: str = "") -> dict | None:
    if isinstance(value, bool):
        value = "Yes" if value else "No"
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    return {"label": label, "value": text, "hint": hint}


def _rows_from_provider(provider: dict, keys: tuple[str, ...]) -> list[dict]:
    rows = []
    for key in keys:
        row = _furnish_row(_PROVIDER_FIELD_LABELS.get(key, key.replace("_", " ").title()), provider.get(key))
        if row:
            rows.append(row)
    return rows


def _digilocker_document_rows(verified: dict, provider: dict, *, unmasked: bool = False) -> list[dict]:
    rows = []
    user = verified.get("user_details") if isinstance(verified.get("user_details"), dict) else {}
    if not user and isinstance(provider.get("user_details"), dict):
        user = provider["user_details"]
    name = str(user.get("name") or verified.get("name") or provider.get("name") or "").strip()
    if name:
        rows.append(_furnish_row("Person name", name))
    for doc in verified.get("documents") or provider.get("documents") or []:
        if not isinstance(doc, dict):
            continue
        doc_type = str(doc.get("type") or "Document")
        doc_name = str(doc.get("name") or "").strip()
        masked = str(doc.get("idMasked") or doc.get("id_masked") or "").strip()
        label = doc_type.replace("_", " ")
        value = " · ".join(part for part in (doc_name, masked) if part) or "Verified"
        rows.append(_furnish_row(label, value))
    if not rows and user:
        for label, keys in (
            ("Aadhaar", ("uid", "eaadhaar", "aadhaar")),
            ("PAN", ("pan",)),
        ):
            for key in keys:
                value = user.get(key)
                display = value if unmasked else _mask_provider_scalar(key, value)
                if display:
                    rows.append(_furnish_row(label, display))
                    break
    return [row for row in rows if row]


def furnish_verification_record(record, *, unmasked: bool = False) -> dict:
    """Human-readable verification summary for staff review templates."""
    provider_raw = record.get_provider_response()
    provider = provider_raw if unmasked else display_provider_payload(provider_raw)
    verified = _verification_verified_data(record, unmasked=unmasked)

    outcome: list[dict] = []
    identifier = record.get_document() if unmasked else record.document_masked
    if identifier:
        outcome.append(_furnish_row("Identifier checked", identifier))
    if record.verified_name:
        outcome.append(_furnish_row("Name at source", record.verified_name))
    if record.verified_dob:
        outcome.append(_furnish_row("Date of birth", record.verified_dob))
    if record.verified_gender:
        outcome.append(_furnish_row("Gender", record.verified_gender))
    outcome = [row for row in outcome if row]

    type_rows = _rows_from_provider(provider, _TYPE_PROVIDER_FIELDS.get(record.verification_type, ()))
    if record.verification_type in {"DIGILOCKER", "AADHAAR"}:
        type_rows = _digilocker_document_rows(verified, provider, unmasked=unmasked)

    address_parts = [
        record.verified_address,
        record.verified_city,
        record.verified_state,
        record.verified_pincode,
    ]
    address_line = ", ".join(part for part in address_parts if part)
    location_rows = []
    if address_line:
        location_rows.append(_furnish_row("Address on record", address_line))
    if record.verified_district:
        location_rows.append(_furnish_row("District", record.verified_district))

    timeline = [
        row
        for row in (
            _furnish_row("Requested", record.requested_at.strftime("%d %b %Y, %H:%M") if record.requested_at else ""),
            _furnish_row("Completed", record.completed_at.strftime("%d %b %Y, %H:%M") if record.completed_at else ""),
            _furnish_row("Expires", record.expires_at.strftime("%d %b %Y") if record.expires_at else ""),
            _furnish_row("Cashfree reference", record.reference_id),
            _furnish_row("Reuse", "Copied from an earlier verification" if record.reused_from_id else ""),
        )
        if row
    ]

    match_percent = None
    if record.name_match_score is not None:
        try:
            match_percent = int(float(record.name_match_score) * 100)
        except (TypeError, ValueError):
            match_percent = None

    sections = []
    if outcome:
        sections.append({"title": "Outcome", "rows": outcome})
    if type_rows:
        sections.append({"title": "Registry details", "rows": type_rows})
    if location_rows:
        sections.append({"title": "Address", "rows": location_rows})
    if timeline:
        sections.append({"title": "Timeline", "rows": timeline})

    highlights = []
    if record.verified_name:
        highlights.append(record.verified_name)
    if identifier:
        highlights.append(identifier)
    if record.name_match_category:
        highlights.append(record.name_match_category.replace("_", " ").title())

    verified_rows = _provider_payload_rows(verified)
    provider_json = format_review_json(provider_raw) if unmasked and provider_raw else ""
    if verified_rows:
        sections.append({"title": "Verified data", "rows": verified_rows})

    return {
        "sections": sections,
        "highlights": highlights,
        "match_percent": match_percent,
        "match_category": (record.name_match_category or "").replace("_", " ").title(),
        "failure": record.display_reason if record.failure_reason else "",
        "provider_json": provider_json,
        "has_provider_json": bool(provider_json),
    }


def verification_records_for_review(records, *, unmasked: bool = False) -> list[dict]:
    return [
        {
            "record": record,
            "furnished": furnish_verification_record(record, unmasked=unmasked),
        }
        for record in records
    ]


def staff_review_context(*, request, merchant, application, verifications) -> dict:
    """Bundle review, verification cards, and risk scores for staff portals."""
    from access.policy import Policy
    from audit.services import AuditService

    from .scoring import compute_review_scores

    unmasked = Policy.can(request.user, "merchant.manage", merchant) or Policy.can(
        request.user, "merchant.review", merchant
    )
    if unmasked:
        AuditService.record(
            actor=request.user,
            action="merchant.pii_reveal",
            resource_type="merchant",
            resource_id=merchant.public_id,
            request=request,
        )
    review = application_review_context(application, unmasked=unmasked)
    verification_cards = verification_records_for_review(verifications, unmasked=unmasked)
    scores = compute_review_scores(
        merchant=merchant,
        application=application,
        records=verifications,
    )
    return {
        "review": review,
        "verification_cards": verification_cards,
        "scores": scores,
        "unmasked": unmasked,
    }


def _human_file_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def documents_for_review(documents) -> list[dict]:
    cards = []
    for document in documents:
        preview_url = ""
        file_name = ""
        file_size = ""
        file_kind = "other"
        if document.file:
            file_name = document.file.name.rsplit("/", 1)[-1]
            try:
                file_size = _human_file_size(document.file.size)
            except (OSError, ValueError):
                file_size = ""
            lower = file_name.lower()
            if lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                file_kind = "image"
                if settings.DEBUG:
                    preview_url = f"/media/{document.file.name}"
            elif lower.endswith(".pdf"):
                file_kind = "pdf"
        cards.append(
            {
                "document": document,
                "preview_url": preview_url,
                "file_name": file_name,
                "file_size": file_size,
                "file_kind": file_kind,
            }
        )
    return cards
