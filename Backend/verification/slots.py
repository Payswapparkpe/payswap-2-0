"""Wizard upload slots to `Document.DocType`.

The Angular wizard identifies every dropzone by a `slotId`. Several slots share
one coarse document type (both KYC person uploads are Aadhaar/PAN scans, every
deed is a registry document), so the slot is stored alongside the type rather
than replacing it.
"""

from .models import Document

SLOT_DOC_TYPES: dict[str, str] = {
    "moa": Document.DocType.MOA,
    "aoa": Document.DocType.AOA,
    "board_resolution": Document.DocType.BOARD_RESOLUTION,
    "auth_letter": Document.DocType.AUTH_LETTER,
    "trustee_resolution": Document.DocType.TRUSTEE_RESOLUTION,
    "partnership_deed": Document.DocType.PARTNERSHIP_DEED,
    "trust_deed": Document.DocType.TRUST_DEED,
    "bank_proof": Document.DocType.BANK_PROOF,
    "penny_proof": Document.DocType.BANK_PROOF,
    "auth_signatory_aadhaar": Document.DocType.AADHAAR,
    "auth_signatory_pan": Document.DocType.PAN,
    "signatory_aadhaar": Document.DocType.AADHAAR,
    "signatory_pan": Document.DocType.PAN,
    "owner_aadhaar": Document.DocType.AADHAAR,
    "owner_pan": Document.DocType.PAN,
    "pan": Document.DocType.PAN,
    "gst": Document.DocType.GST,
    "coi": Document.DocType.COI,
}


def normalize_slot_id(value: str) -> str:
    return "".join(ch for ch in (value or "").strip().lower() if ch.isalnum() or ch == "_")[:40]


def doc_type_for_slot(slot_id: str) -> str:
    """Resolve a wizard slot to a document type, falling back to OTHER.

    An unknown slot must not fail the upload — the reviewer still needs the file,
    and `slot_id` preserves exactly which dropzone produced it.
    """
    slot = normalize_slot_id(slot_id)
    if slot in SLOT_DOC_TYPES:
        return SLOT_DOC_TYPES[slot]
    upper = slot.upper()
    if upper in Document.DocType.values:
        return upper
    return Document.DocType.OTHER
