class ApplicationStatus:
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    CHOICES = [
        (DRAFT, "Draft"),
        (SUBMITTED, "Submitted"),
        (UNDER_REVIEW, "Under review"),
        (CLARIFICATION_REQUIRED, "Clarification required"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    TRANSITIONS = {
        DRAFT: {SUBMITTED},
        SUBMITTED: {UNDER_REVIEW},
        UNDER_REVIEW: {APPROVED, REJECTED, CLARIFICATION_REQUIRED},
        CLARIFICATION_REQUIRED: {SUBMITTED},
        APPROVED: set(),
        REJECTED: set(),
    }


class StepStatus:
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    NEEDS_CORRECTION = "NEEDS_CORRECTION"
    LOCKED = "LOCKED"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    CHOICES = [
        (NOT_STARTED, "Not started"),
        (IN_PROGRESS, "In progress"),
        (COMPLETE, "Complete"),
        (NEEDS_CORRECTION, "Needs correction"),
        (LOCKED, "Locked"),
        (SUBMITTED, "Submitted"),
        (UNDER_REVIEW, "Under review"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]


ONBOARDING_STEPS = [
    ("account", "Account"),
    ("business", "Business"),
    ("owners", "Owners"),
    ("kyc", "KYC"),
    ("kyb", "KYB"),
    ("bank", "Bank"),
    ("documents", "Documents"),
    ("review", "Review"),
    ("agreement", "Agreement"),
    ("activation", "Activation"),
]

REQUIRED_BEFORE_SUBMIT = ["account", "business", "owners", "kyc", "kyb", "bank", "documents", "review"]

# Merchant-facing wizard. Database still stores every ONBOARDING_STEPS key;
# KYC/KYB are filled from the business step so identifiers are collected once.
WIZARD_PHASES = [
    ("business", "Business", "Legal name, PAN, GSTIN, and registered address — collected once."),
    ("owners", "People", "Owners and the person who will sign the agreement."),
    ("bank", "Bank", "Settlement account for payouts."),
    ("documents", "Documents", "Upload supporting files. Checks run after you submit."),
    ("review", "Review", "Confirm the file, then send it for verification."),
]
WIZARD_KEYS = [key for key, _title, _hint in WIZARD_PHASES]
WIZARD_ALIASES = {
    "account": "business",
    "kyc": "business",
    "kyb": "business",
    "agreement": "review",
    "activation": "review",
}


def normalize_wizard_key(key: str | None) -> str:
    if key in WIZARD_KEYS:
        return key
    return WIZARD_ALIASES.get(key or "", "business")


def next_wizard_key(key: str) -> str | None:
    current = normalize_wizard_key(key)
    index = WIZARD_KEYS.index(current)
    if index + 1 < len(WIZARD_KEYS):
        return WIZARD_KEYS[index + 1]
    return None


def prev_wizard_key(key: str) -> str | None:
    current = normalize_wizard_key(key)
    index = WIZARD_KEYS.index(current)
    if index > 0:
        return WIZARD_KEYS[index - 1]
    return None


def first_incomplete_wizard_key(application) -> str:
    by_key = {step.key: step.status for step in application.steps.all()}
    for key in WIZARD_KEYS:
        if by_key.get(key) != StepStatus.COMPLETE:
            return key
    return "review"


ENTITY_BUSINESS_FIELDS = {
    "INDIVIDUAL": ["legal_name", "pan"],
    "PROPRIETORSHIP": ["legal_name", "pan"],
    "PARTNERSHIP": ["legal_name", "pan"],
    "LLP": ["legal_name", "llpin", "pan"],
    "PRIVATE_LIMITED": ["legal_name", "cin", "pan", "gstin"],
    "PUBLIC_LIMITED": ["legal_name", "cin", "pan", "gstin"],
    "TRUST": ["legal_name", "pan"],
    "SOCIETY": ["legal_name", "pan"],
    "HUF": ["legal_name", "pan"],
}

# Shown on the business step but never mandatory — they enrich the agreement
# and enable PIN-code autofill without blocking onboarding.
OPTIONAL_BUSINESS_FIELDS = ["registered_office", "pincode"]

FIELD_LABELS = {
    "legal_name": "Legal name",
    "pan": "PAN",
    "gstin": "GSTIN",
    "cin": "CIN",
    "llpin": "LLPIN",
    "registered_office": "Registered office address",
    "pincode": "PIN code",
    "owner_name": "Owner / director name",
    "designation": "Designation",
    "authorized_signatory": "Authorized signatory",
    "ownership_percent": "Ownership percent",
    "owner_dob": "Signatory date of birth",
    "aadhaar": "Aadhaar (optional)",
    "account_holder": "Account holder name",
    "account_number": "Account number",
    "ifsc": "IFSC",
    "notes": "Notes",
}

STEP_FIELDS = {
    "owners": [
        "owner_name",
        "designation",
        "authorized_signatory",
        "ownership_percent",
        "owner_dob",
        "aadhaar",
    ],
    "kyc": ["pan"],
    "kyb": ["gstin", "cin"],
    "bank": ["account_holder", "account_number", "ifsc"],
    "documents": [],
    "review": [],
    "agreement": [],
    "activation": [],
}
