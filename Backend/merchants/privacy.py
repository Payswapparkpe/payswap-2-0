"""PII handling for onboarding step payloads.

PAN, GSTIN, CIN and LLPIN collected during onboarding are Fernet-encrypted at
rest inside ``OnboardingStep.data``. Plaintext is only ever reconstructed for
two privileged consumers: agreement rendering and provider verification.
Every display surface works with masked values ("••••••1234F").
"""

from core.crypto import decrypt_text, encrypt_text

SENSITIVE_STEP_KEYS = frozenset({"pan", "gstin", "cin", "llpin", "aadhaar"})

# Fernet tokens always begin with the base64 of the 0x80 version byte.
_FERNET_PREFIX = "gAAAA"

MASK_BULLET = "•"


def _is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(_FERNET_PREFIX)


def encrypt_step_data(data: dict) -> dict:
    """Return a copy of *data* with sensitive keys encrypted (idempotent)."""
    protected = dict(data)
    for key in SENSITIVE_STEP_KEYS:
        value = protected.get(key)
        if value and not _is_encrypted(str(value)):
            protected[key] = encrypt_text(str(value).strip())
    return protected


def decrypt_step_data(data: dict | None) -> dict:
    """Return a plaintext copy. Legacy plaintext values pass through unchanged
    so rows written before encryption-at-rest remain readable."""
    revealed = dict(data or {})
    for key in SENSITIVE_STEP_KEYS:
        value = revealed.get(key)
        if value and _is_encrypted(str(value)):
            revealed[key] = decrypt_text(str(value))
    return revealed


def mask_step_value(key: str, value) -> str:
    """Mask a sensitive plaintext-or-encrypted value to its last four chars."""
    text = str(value or "")
    if key not in SENSITIVE_STEP_KEYS or not text:
        return text
    if _is_encrypted(text):
        text = decrypt_text(text)
    return MASK_BULLET * max(len(text) - 4, 0) + text[-4:]


def display_step_data(data: dict | None) -> dict:
    """Display-safe copy: ordinary fields in clear, sensitive fields masked."""
    revealed = decrypt_step_data(data)
    return {key: mask_step_value(key, value) for key, value in revealed.items()}


def merge_step_data(existing_plain: dict, submitted: dict) -> dict:
    """Merge a form submission over the existing plaintext step data.

    Sensitive fields rendered as masked placeholders must not overwrite the
    stored value: a blank input or a resubmitted masked value keeps the
    previous entry. Everything else replaces as usual.
    """
    merged = dict(existing_plain)
    for key, value in (submitted or {}).items():
        text = str(value).strip()
        if key in SENSITIVE_STEP_KEYS and existing_plain.get(key) and (not text or MASK_BULLET in text):
            continue
        merged[key] = value
    return merged
