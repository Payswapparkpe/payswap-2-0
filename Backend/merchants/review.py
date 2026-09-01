"""Reviewer-facing view of a submitted onboarding application.

Both the administration merchant detail page and the employee KYC queue render
the same application, so the sections are built once here. Values arrive already
masked by :func:`display_step_data` — no template ever sees a full PAN.
"""

from .models import Merchant
from .privacy import display_step_data

#: Sections a reviewer can send back for correction. Admin and employee portals
#: must offer the same list, otherwise a send-back means different things.
CLARIFICATION_SECTIONS = [
    ("business", "Business details"),
    ("owners", "People & ownership"),
    ("bank", "Bank account"),
    ("documents", "Documents"),
]

_ADDRESS_PARTS = ("registered_office", "city", "state", "pincode")


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


def _registry_rows(entries, *, empty: str) -> dict:
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
    return {"rows": rows, "empty": empty}


def application_review_context(application) -> dict:
    """Masked, section-grouped application data for the review templates."""
    if application is None:
        return {"available": False, "sections": [], "people": [], "steps": {}}

    steps = {step.key: display_step_data(step.data) for step in application.steps.all()}
    business = steps.get("business") or {}
    owners = steps.get("owners") or {}
    bank = steps.get("bank") or {}
    review = steps.get("review") or {}
    compliance = review.get("compliance") or {}
    entity_type = application.merchant.entity_type

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

    address = ", ".join(str(business.get(part) or "").strip() for part in _ADDRESS_PARTS if business.get(part))

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
                _row("Registered office", address),
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

    return {
        "available": True,
        "sections": sections,
        "people": _people_sections(business, owners),
        "signatory_is_owner": business.get("signatory_is_owner"),
        "kyc_person_is_authorised_signatory": business.get("kyc_person_is_authorised_signatory"),
        "signatory_relation": owners.get("designation") or "",
        "directors": _registry_rows(
            business.get("registry_directors"), empty="No directors fetched from the registry."
        ),
        "members": _registry_rows(
            business.get("registry_members"), empty="No partners or trustees recorded."
        ),
        "ubos": _registry_rows(business.get("ubos"), empty="No beneficial owners declared."),
        "uploaded_slots": (steps.get("documents") or {}).get("slots") or [],
        "steps": steps,
    }
