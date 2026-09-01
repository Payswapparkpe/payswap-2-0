"""Provider abstraction for identity verification.

Application services call ``VerificationProvider`` methods and receive a
normalized ``ProviderResult``; they never see transport details. The Cashfree
implementation maps Secure ID responses onto our internal status vocabulary
(``VerificationRecord.Status``). A second provider can be added by implementing
the same interface without touching domain code.
"""

from dataclasses import dataclass, field
from typing import Protocol

from integrations.cashfree import CashfreeClient


@dataclass
class ProviderResult:
    status: str  # VerificationRecord.Status value
    reference_id: str = ""
    name: str = ""
    dob: str = ""
    gender: str = ""
    address: str = ""
    state: str = ""
    city: str = ""
    district: str = ""
    pincode: str = ""
    name_match_score: float | None = None
    name_match_category: str = ""
    failure_reason: str = ""
    data: dict = field(default_factory=dict)  # curated, display-safe fields
    raw: dict = field(default_factory=dict)  # full payload — encrypted at rest


class VerificationProvider(Protocol):
    def verify_pan(self, *, verification_id: str, pan: str, name: str, dob: str) -> ProviderResult: ...
    def verify_gstin(self, *, gstin: str) -> ProviderResult: ...
    def verify_bank(self, *, account_number: str, ifsc: str, name: str) -> ProviderResult: ...
    def verify_ifsc(self, *, verification_id: str, ifsc: str) -> ProviderResult: ...


class CashfreeVerificationProvider:
    def __init__(self, client: CashfreeClient):
        self.client = client

    def verify_pan(self, *, verification_id: str, pan: str, name: str, dob: str) -> ProviderResult:
        data = self.client.verify_pan_lite(verification_id=verification_id, pan=pan, name=name, dob=dob)
        pan_status = str(data.get("pan_status") or data.get("status") or "").upper()
        name_match = str(data.get("name_match") or "").upper()
        valid = pan_status in {"VALID", "ACTIVE"} or str(data.get("valid")).lower() == "true"
        status = "VERIFIED" if valid else "FAILED"
        if valid and name_match in {"PARTIAL", "NO_MATCH"}:
            status = "PARTIALLY_VERIFIED"
        return ProviderResult(
            status=status,
            reference_id=str(data.get("reference_id") or ""),
            name=str(data.get("name") or data.get("registered_name") or "")[:150],
            dob=str(data.get("dob") or "")[:10],
            name_match_category=name_match,
            failure_reason="" if valid else "PAN could not be verified at source.",
            data={
                "pan_status": pan_status,
                "name_match": name_match,
                "aadhaar_seeding_status": data.get("aadhaar_seeding_status"),
            },
            raw=data,
        )

    def verify_gstin(self, *, gstin: str) -> ProviderResult:
        data = self.client.verify_gstin(gstin=gstin)
        gst_status = str(data.get("gst_in_status") or "").lower()
        valid = gst_status == "active"
        return ProviderResult(
            status="VERIFIED" if valid else "FAILED",
            reference_id=str(data.get("reference_id") or ""),
            name=str(data.get("legal_name_of_business") or "")[:150],
            address=str(data.get("principal_place_address") or ""),
            failure_reason="" if valid else f"GSTIN status is {gst_status or 'unknown'}.",
            data={
                "gst_in_status": data.get("gst_in_status"),
                "legal_name_of_business": data.get("legal_name_of_business"),
                "trade_name_of_business": data.get("trade_name_of_business"),
                "constitution_of_business": data.get("constitution_of_business"),
                "taxpayer_type": data.get("taxpayer_type"),
                "date_of_registration": data.get("date_of_registration"),
                "principal_place_address": data.get("principal_place_address"),
            },
            raw=data,
        )

    def verify_bank(self, *, account_number: str, ifsc: str, name: str) -> ProviderResult:
        data = self.client.verify_bank_sync(bank_account=account_number, ifsc=ifsc, name=name)
        account_status = str(data.get("account_status") or data.get("status") or "").upper()
        valid = account_status in {"VALID", "SUCCESS", "ACTIVE"} or str(
            data.get("account_exists") or ""
        ).upper() in {"YES", "TRUE"}
        name_score = data.get("name_match_score")
        try:
            name_score = float(name_score) if name_score is not None else None
        except (TypeError, ValueError):
            name_score = None
        status = "VERIFIED" if valid else "FAILED"
        if valid and name_score is not None and name_score < 0.6:
            status = "PARTIALLY_VERIFIED"
        return ProviderResult(
            status=status,
            reference_id=str(data.get("reference_id") or ""),
            name=str(data.get("name_at_bank") or "")[:150],
            name_match_score=name_score,
            name_match_category=str(data.get("name_match_result") or "").upper(),
            failure_reason="" if valid else "Bank account could not be verified.",
            data={
                "account_status": account_status,
                "name_at_bank": data.get("name_at_bank"),
                "bank_name": data.get("bank_name"),
                "ifsc": data.get("ifsc"),
                "utr": data.get("utr"),
            },
            raw=data,
        )

    def verify_ifsc(self, *, verification_id: str, ifsc: str) -> ProviderResult:
        data = self.client.verify_ifsc(verification_id=verification_id, ifsc=ifsc)
        valid = str(data.get("status") or "").upper() == "VALID"
        return ProviderResult(
            status="VERIFIED" if valid else "FAILED",
            reference_id=str(data.get("reference_id") or ""),
            address=str(data.get("address") or ""),
            state=str(data.get("state") or "")[:60],
            city=str(data.get("city") or "")[:60],
            failure_reason="" if valid else "IFSC not recognised.",
            data={
                "bank": data.get("bank"),
                "branch": data.get("branch"),
                "address": data.get("address"),
                "city": data.get("city"),
                "state": data.get("state"),
                "ifsc": data.get("ifsc"),
                "neft": data.get("neft"),
                "imps": data.get("imps"),
                "rtgs": data.get("rtgs"),
                "upi": data.get("upi"),
            },
            raw=data,
        )
