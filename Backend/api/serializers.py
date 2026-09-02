"""Map Django domain objects to Angular console shapes."""

from django.conf import settings
from django.core.exceptions import ValidationError

from accounts.models import User
from agreements.models import Agreement
from catalog.models import VoucherProduct
from merchants.models import Merchant, OnboardingApplication
from merchants.privacy import decrypt_step_data
from merchants.states import ApplicationStatus, StepStatus, WIZARD_KEYS
from orders.models import OrderStatus, PaymentOrder


def user_payload(user: User) -> dict:
    return {
        "id": str(user.pk),
        "publicId": user.public_id,
        "fullName": user.name or user.display_name,
        "email": user.email,
        "mobile": user.mobile or "",
        "password": "",
        "partnerType": "corporate",
        "mobileVerified": bool(user.mobile_verified_at),
        "emailVerified": bool(user.email_verified_at),
        "createdAt": user.date_joined.isoformat(),
    }


def _address_from_business(data: dict) -> dict:
    office = (data.get("registered_office") or data.get("address") or "").strip()
    return {
        "line1": office,
        "line2": "",
        "city": (data.get("city") or "").strip(),
        "state": (data.get("state") or "").strip(),
        "pin": (data.get("pincode") or "").strip(),
    }


def _address_to_storage(address: dict | None) -> dict:
    address = address or {}
    return {
        "line1": (address.get("line1") or "")[:200],
        "line2": (address.get("line2") or "")[:200],
        "city": (address.get("city") or "")[:80],
        "state": (address.get("state") or "")[:80],
        "pin": (address.get("pin") or "")[:6],
    }


def _documents_to_storage(docs) -> list[dict]:
    """Keep uploaded-document references only; file bytes live in the Document model."""
    stored = []
    for doc in docs or []:
        if not isinstance(doc, dict):
            continue
        stored.append(
            {
                "slotId": doc.get("slotId") or "",
                "publicId": doc.get("publicId") or "",
                "fileName": doc.get("fileName") or "",
                "fileSize": int(doc.get("fileSize") or 0),
                "mimeType": doc.get("mimeType") or "application/octet-stream",
                "ocrPayload": doc.get("ocrPayload") or None,
            }
        )
    return stored


def _documents_to_angular(docs) -> list[dict]:
    payload = []
    for doc in docs or []:
        if not isinstance(doc, dict):
            continue
        payload.append(
            {
                "slotId": doc.get("slotId") or "",
                "publicId": doc.get("publicId") or "",
                "fileName": doc.get("fileName") or "",
                "fileSize": int(doc.get("fileSize") or 0),
                "mimeType": doc.get("mimeType") or "application/octet-stream",
                "ocrPayload": doc.get("ocrPayload") or None,
            }
        )
    return payload


_DOC_REVIEW_STATES = {
    "UPLOADED": "uploaded",
    "UNDER_REVIEW": "under_review",
    "VERIFIED": "verified",
    "ACTION_REQUIRED": "action_required",
    "REJECTED": "rejected",
}


def document_payload(doc) -> dict:
    """Shape a stored Document for the wizard's UploadedDoc slot state."""
    try:
        file_size = doc.file.size if doc.file else 0
    except (OSError, ValueError):
        # The row can outlive its file in local/dev storage; the slot must still render.
        file_size = 0
    return {
        "slotId": doc.slot_id or doc.doc_type.lower(),
        "publicId": doc.public_id,
        "docType": doc.doc_type,
        "fileName": doc.file.name.rsplit("/", 1)[-1] if doc.file else doc.public_id,
        "fileSize": file_size,
        "mimeType": "application/octet-stream",
        "uploadStatus": "uploaded",
        "reviewStatus": _DOC_REVIEW_STATES.get(doc.status, "uploaded"),
        "rejectionReason": doc.rejection_reason or "",
    }


def _person_kyc_to_storage(person: dict | None) -> dict:
    """Normalize an Angular SignatoryKyc object for storage inside step data.

    The nested ``pan`` is encrypted by ``encrypt_step_data`` along with every
    other sensitive key, so this stays plaintext only in memory.
    """
    person = person or {}
    return {
        "name": (person.get("name") or "").strip()[:150],
        "pan": (person.get("pan") or "").strip().upper(),
        "dob": (person.get("dob") or "").strip()[:10],
        "mobile": (person.get("mobile") or "").strip()[:15],
        "path": person.get("path") or "digilocker",
        "verified": bool(person.get("verified")),
        "digilocker_failed": bool(person.get("digilockerFailed")),
        "digilocker": person.get("digilocker") or None,
        "address": _address_to_storage(person.get("address")),
        "docs": _documents_to_storage(person.get("docs")),
    }


def _person_kyc_to_angular(
    stored: dict | None, *, fallback_name: str = "", fallback_mobile: str = "", fallback_address: dict | None = None
) -> dict:
    stored = stored or {}
    address = stored.get("address") or {}
    has_address = any((address.get(part) or "").strip() for part in ("line1", "city", "state", "pin"))
    return {
        "name": stored.get("name") or fallback_name,
        "pan": stored.get("pan") or "",
        "dob": stored.get("dob") or "",
        "mobile": stored.get("mobile") or fallback_mobile,
        "path": stored.get("path") or "digilocker",
        "verified": bool(stored.get("verified")),
        "digilockerFailed": bool(stored.get("digilocker_failed")),
        "digilocker": stored.get("digilocker") or None,
        "address": address if has_address else (fallback_address or _address_to_storage(None)),
        "docs": _documents_to_angular(stored.get("docs")),
    }


def _registry_check_to_storage(check: dict | None) -> dict | None:
    """Persist a Cashfree registry result so the verified badge survives a reload."""
    if not isinstance(check, dict) or not check.get("status"):
        return None
    return {
        "verificationId": check.get("verificationId") or "",
        "referenceId": int(check.get("referenceId") or 0),
        "status": str(check.get("status") or "").upper(),
        "registeredName": (check.get("registeredName") or "")[:150],
    }


def _registry_check_to_angular(stored: dict | None) -> dict | None:
    if not isinstance(stored, dict) or not stored.get("status"):
        return None
    return {
        "verificationId": stored.get("verificationId") or "",
        "referenceId": int(stored.get("referenceId") or 0),
        "status": stored.get("status") or "",
        "registeredName": stored.get("registeredName") or "",
    }


def _stored_flag(stored) -> bool | None:
    """Branching answers are tri-state: null until the merchant actually answers.

    Returning a hardcoded ``True`` here would silently assert that the account
    opener is the owner and skip the owner/auth-signatory branches entirely.
    """
    return stored if isinstance(stored, bool) else None


def _entity_type_to_angular(value: str) -> str:
    mapping = {
        Merchant.EntityType.INDIVIDUAL: "individual",
        Merchant.EntityType.PROPRIETORSHIP: "proprietorship",
        Merchant.EntityType.PARTNERSHIP: "partnership",
        Merchant.EntityType.LLP: "llp",
        Merchant.EntityType.PRIVATE_LIMITED: "private_limited",
        Merchant.EntityType.PUBLIC_LIMITED: "public_limited",
        Merchant.EntityType.TRUST: "trust_society_ngo",
        Merchant.EntityType.SOCIETY: "trust_society_ngo",
        Merchant.EntityType.HUF: "huf",
    }
    return mapping.get(value or Merchant.EntityType.INDIVIDUAL, "individual")


def _entity_type_from_angular(value: str) -> str:
    mapping = {
        "individual": Merchant.EntityType.INDIVIDUAL,
        "proprietorship": Merchant.EntityType.PROPRIETORSHIP,
        "partnership": Merchant.EntityType.PARTNERSHIP,
        "llp": Merchant.EntityType.LLP,
        "private_limited": Merchant.EntityType.PRIVATE_LIMITED,
        "public_limited": Merchant.EntityType.PUBLIC_LIMITED,
        "opc": Merchant.EntityType.PRIVATE_LIMITED,
        "trust_society_ngo": Merchant.EntityType.TRUST,
        "huf": Merchant.EntityType.HUF,
    }
    return mapping.get((value or "").lower(), Merchant.EntityType.INDIVIDUAL)


def _account_status(application: OnboardingApplication | None, merchant: Merchant | None) -> str:
    if application is None:
        return "registered"
    status = application.status
    if status == ApplicationStatus.DRAFT:
        return "draft"
    if status in {ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW}:
        return "under_review"
    if status == ApplicationStatus.CLARIFICATION_REQUIRED:
        return "draft"
    if status == ApplicationStatus.REJECTED:
        return "draft"
    if status == ApplicationStatus.APPROVED:
        if merchant and merchant.commercial_status == Merchant.CommercialStatus.ACTIVE:
            return "activated"
        if merchant and merchant.agreement_status == Merchant.VerificationState.VERIFIED:
            return "pending_admin_sign"
        return "pending_agreement"
    return "registered"


def _current_step(application: OnboardingApplication | None) -> str:
    if application is None:
        return "signatory"
    for key in WIZARD_KEYS:
        step = application.steps.filter(key=key).first()
        if step is None:
            continue
        if step.status not in {"COMPLETE", "SUBMITTED", "APPROVED"}:
            alias = {
                "business": "profile",
                "owners": "ubo",
                "bank": "bank",
                "documents": "documents",
                "review": "review",
            }
            if (
                step.key == "owners"
                and application.merchant.entity_type == Merchant.EntityType.INDIVIDUAL
            ):
                continue
            if step.key == "business" and step.status == StepStatus.IN_PROGRESS:
                data = decrypt_step_data(step.data)
                entity = application.merchant.entity_type
                if entity != Merchant.EntityType.INDIVIDUAL:
                    if not (data.get("owner_name") or "").strip():
                        return "signatory"
                    if not (data.get("pan") or "").strip() or (
                        entity
                        in {
                            Merchant.EntityType.PRIVATE_LIMITED,
                            Merchant.EntityType.PUBLIC_LIMITED,
                            Merchant.EntityType.LLP,
                        }
                        and not (data.get("cin") or data.get("llpin") or "").strip()
                    ):
                        return "identity"
            return alias.get(key, "profile")
    return "review"


def _correction_steps(application: OnboardingApplication | None) -> list[str]:
    """Angular wizard steps where admin requested reverification."""
    if not application or application.status != ApplicationStatus.CLARIFICATION_REQUIRED:
        return []
    key_to_steps = {
        "business": ["profile", "identity"],
        "owners": ["signatory", "owner", "auth_signatory", "ubo"],
        "bank": ["bank"],
        "documents": ["documents"],
        "kyc": ["signatory", "auth_signatory"],
        "kyb": ["identity"],
        "review": ["review"],
    }
    steps: list[str] = []
    for step in application.steps.filter(status=StepStatus.NEEDS_CORRECTION):
        steps.extend(key_to_steps.get(step.key, []))
    return list(dict.fromkeys(steps))


def onboarding_payload(*, user: User, application: OnboardingApplication | None, merchant: Merchant | None) -> dict:
    business = {}
    owners = {}
    bank = {}
    review = {}
    if application:
        for step in application.steps.all():
            data = decrypt_step_data(step.data)
            if step.key == "business":
                business = data
            elif step.key == "owners":
                owners = data
            elif step.key == "bank":
                bank = data
            elif step.key == "review":
                review = data
    stored_compliance = review.get("compliance") or {}

    documents = [document_payload(doc) for doc in merchant.documents.all()[:50]] if merchant else []
    # Every dropzone posts to the same upload endpoint, so the stored rows are the
    # single source of truth for slot state — including the two standalone slots.
    docs_by_slot = {doc["slotId"]: doc for doc in documents}

    agreement = _agreement_embed(merchant)
    registered = _address_from_business(business)
    registry_directors = business.get("registry_directors") or []
    stored_ubos = business.get("ubos") or []
    ubos = []
    for item in stored_ubos:
        if not isinstance(item, dict):
            continue
        ubos.append(
            {
                "id": str(item.get("id") or ""),
                "name": item.get("name") or "",
                "pan": item.get("pan") or "",
                "ownershipPercent": float(item.get("ownershipPercent") or item.get("ownership_percent") or 0),
                "relationship": item.get("relationship") or item.get("designation") or "Director",
                "kycVerified": bool(item.get("kycVerified") or item.get("kyc_verified")),
            }
        )
    if not ubos and registry_directors:
        for director in registry_directors[:10]:
            if not isinstance(director, dict):
                continue
            ubos.append(
                {
                    "id": str(director.get("din") or director.get("name") or ""),
                    "name": director.get("name") or "",
                    "pan": director.get("pan") or "",
                    "ownershipPercent": 0,
                    "relationship": director.get("designation") or "Director",
                    "kycVerified": bool(
                        director.get("kycVerified") or director.get("kyc_verified")
                    ),
                }
            )
    return_reason = ""
    if application:
        if application.rejection_notes:
            return_reason = application.rejection_notes
        elif application.status == ApplicationStatus.CLARIFICATION_REQUIRED:
            for step in application.steps.filter(status="NEEDS_CORRECTION"):
                if step.clarification_message:
                    return_reason = step.clarification_message
                    break
    return {
        "userId": user.public_id,
        "merchantId": merchant.public_id if merchant else "",
        "status": _account_status(application, merchant),
        "currentStep": _current_step(application),
        "returnReason": return_reason,
        "correctionSteps": _correction_steps(application),
        "profile": {
            "brandName": business.get("brand_name") or merchant.business_name if merchant else "",
            "legalName": business.get("legal_name") or (merchant.business_name if merchant else ""),
            "entityType": _entity_type_to_angular(merchant.entity_type if merchant else ""),
            "category": business.get("category") or "",
            "subCategory": business.get("sub_category") or "",
            "website": business.get("website") or "",
            "monthlyVolume": business.get("monthly_volume") or "",
            "gstin": business.get("gstin") or "",
            "noGstin": bool(business.get("no_gstin")) or not bool(business.get("gstin")),
            "gstinOptions": [],
        },
        "registryDirectors": registry_directors,
        "registryMembers": business.get("registry_members") or [],
        "identity": {
            "pan": business.get("pan") or "",
            "doi": business.get("doi") or "",
            "cin": business.get("cin") or "",
            "llpin": business.get("llpin") or "",
            "registeredAddress": registered,
            "operatingAddress": registered,
            "sameAsRegistered": True,
            "panCheck": _registry_check_to_angular(business.get("pan_check")),
            "gstinCheck": _registry_check_to_angular(business.get("gstin_check")),
            "cinCheck": _registry_check_to_angular(business.get("cin_check")),
            "gstinOptions": [],
            "udyamNumber": business.get("udyam_number") or "",
            "udyamCheck": (
                {
                    "verificationId": business.get("udyam_verification_id") or "",
                    "referenceId": int(business.get("udyam_reference_id") or 0),
                    "status": "VALID",
                    "registeredName": business.get("udyam_enterprise_name")
                    or business.get("legal_name")
                    or "",
                }
                if business.get("udyam_verified")
                else None
            ),
            "udyamDetails": business.get("udyam_details") or None,
        },
        "signatory": _person_kyc_to_angular(
            business.get("signatory_kyc"),
            fallback_name=owners.get("owner_name") or owners.get("authorized_signatory") or user.name,
            fallback_mobile=user.mobile or "",
            fallback_address=registered,
        )
        | {
            "verified": bool(
                (business.get("signatory_kyc") or {}).get("verified")
                or business.get("signatory_verified")
                or (merchant and merchant.kyc_status == Merchant.VerificationState.VERIFIED)
            ),
        },
        "kycPersonIsAuthorisedSignatory": _stored_flag(
            business.get("kyc_person_is_authorised_signatory")
        ),
        "signatoryRelation": owners.get("designation") or "",
        "authorisedSignatoryName": owners.get("authorized_signatory") or "",
        "signatoryIsOwner": _stored_flag(business.get("signatory_is_owner")),
        "ownerKyc": _person_kyc_to_angular(
            owners.get("owner_kyc"),
            fallback_name=owners.get("owner_name") or "",
            fallback_mobile=user.mobile or "",
            fallback_address=registered,
        ),
        "authSignatoryKyc": _person_kyc_to_angular(
            owners.get("auth_signatory_kyc"),
            fallback_name=owners.get("authorized_signatory") or "",
            fallback_mobile=user.mobile or "",
            fallback_address=registered,
        ),
        "ubos": ubos,
        "ubosFrozen": bool(business.get("ubos_frozen")),
        "publicListedSkip": bool(business.get("public_listed_skip")),
        "bank": {
            "accountNumber": bank.get("account_number") or "",
            "ifsc": bank.get("ifsc") or "",
            "holderName": bank.get("account_holder") or "",
            "accountType": bank.get("account_type") or "current",
            "bankName": bank.get("bank_name") or "",
            "branch": bank.get("branch") or "",
            "pennyDropStatus": "matched"
            if merchant and merchant.bank_status == Merchant.VerificationState.VERIFIED
            else (bank.get("penny_drop_status") or "idle"),
            "proofFile": docs_by_slot.get("penny_proof") or docs_by_slot.get("bank_proof"),
        },
        "documents": documents,
        "registryDeedDoc": docs_by_slot.get("partnership_deed") or docs_by_slot.get("trust_deed"),
        "compliance": {
            "privacyPolicy": bool(stored_compliance.get("privacyPolicy")),
            "refundPolicy": bool(stored_compliance.get("refundPolicy")),
            "terms": bool(stored_compliance.get("terms")),
            "physicalAddress": bool(
                stored_compliance.get("physicalAddress")
                or business.get("registered_office")
                or business.get("pincode")
            ),
            "authorisedDeclaration": bool(stored_compliance.get("authorisedDeclaration")),
            "truthDeclaration": bool(
                stored_compliance.get("truthDeclaration") or review.get("confirmed")
            ),
            "dpdpConsent": bool(stored_compliance.get("dpdpConsent")),
        },
        "agreement": agreement,
        "submittedAt": application.submitted_at.isoformat() if application and application.submitted_at else None,
        "kybApprovedAt": None,
        "activatedAt": None,
    }


def onboarding_step_data_from_angular(step: str, payload: dict) -> tuple[str, dict]:
    """Return (django_step_key, data dict) for MerchantOnboardingService.save_step."""
    if step in {"profile", "identity", "signatory"}:
        profile = payload.get("profile") or {}
        identity = payload.get("identity") or {}
        signatory = payload.get("signatory") or {}
        registered = identity.get("registeredAddress") or {}
        signatory_name = (signatory.get("name") or "").strip()
        udyam_details = identity.get("udyamDetails") or {}
        udyam_owner = (udyam_details.get("ownerName") or "").strip()
        owner_name = udyam_owner or signatory_name
        data = {
            "legal_name": profile.get("legalName") or profile.get("brandName") or signatory_name,
            "brand_name": profile.get("brandName") or signatory_name,
            "entity_type": profile.get("entityType") or "",
            "category": profile.get("category") or "",
            "sub_category": profile.get("subCategory") or "",
            "website": profile.get("website") or "",
            "monthly_volume": profile.get("monthlyVolume") or "",
            "gstin": profile.get("gstin") or "",
            "no_gstin": bool(profile.get("noGstin")),
            "pan": identity.get("pan") or signatory.get("pan") or "",
            "doi": identity.get("doi") or "",
            "cin": identity.get("cin") or "",
            "llpin": identity.get("llpin") or "",
            "registered_office": registered.get("line1") or "",
            "pincode": registered.get("pin") or "",
            "city": registered.get("city") or "",
            "state": registered.get("state") or "",
            "owner_name": owner_name,
            "owner_dob": signatory.get("dob") or "",
            "authorized_signatory": payload.get("authorisedSignatoryName") or signatory_name,
            "designation": payload.get("signatoryRelation") or "",
            "signatory_verified": bool(signatory.get("verified")),
            "registry_directors": identity.get("registryDirectors") or payload.get("registryDirectors") or [],
            "registry_members": identity.get("registryMembers") or payload.get("registryMembers") or [],
            "signatory_kyc": _person_kyc_to_storage(signatory),
            "udyam_number": identity.get("udyamNumber") or "",
            "udyam_verified": bool((identity.get("udyamCheck") or {}).get("status") == "VALID"),
            "udyam_verification_id": (identity.get("udyamCheck") or {}).get("verificationId") or "",
            "udyam_reference_id": (identity.get("udyamCheck") or {}).get("referenceId") or 0,
            "udyam_enterprise_name": (identity.get("udyamCheck") or {}).get("registeredName") or "",
            "udyam_details": identity.get("udyamDetails") or {},
        }
        # Only persist a branching answer once the merchant has actually made one,
        # so an unanswered null never overwrites a stored false.
        for angular_key, storage_key in (
            ("signatoryIsOwner", "signatory_is_owner"),
            ("kycPersonIsAuthorisedSignatory", "kyc_person_is_authorised_signatory"),
        ):
            if isinstance(payload.get(angular_key), bool):
                data[storage_key] = payload[angular_key]
        # Likewise, a step saved before a registry call must not clear an earlier result.
        for angular_key, storage_key in (
            ("panCheck", "pan_check"),
            ("gstinCheck", "gstin_check"),
            ("cinCheck", "cin_check"),
        ):
            check = _registry_check_to_storage(identity.get(angular_key))
            if check:
                data[storage_key] = check
        return "business", data
    if step == "ubo":
        return "business", {
            "ubos": payload.get("ubos") or [],
            "ubos_frozen": bool(payload.get("ubosFrozen")),
            "public_listed_skip": bool(payload.get("publicListedSkip")),
            "registry_directors": payload.get("registryDirectors") or [],
        }
    if step == "auth_signatory":
        auth_signatory = payload.get("authSignatoryKyc") or {}
        signatory = payload.get("signatory") or {}
        signatory_name = (signatory.get("name") or "").strip()
        return "owners", {
            # Flat fields stay authoritative for agreements, name alignment, and matching.
            "owner_name": signatory_name,
            "authorized_signatory": (auth_signatory.get("name") or "").strip()
            or payload.get("authorisedSignatoryName")
            or signatory_name,
            "designation": payload.get("signatoryRelation") or "",
            "auth_signatory_kyc": _person_kyc_to_storage(auth_signatory),
        }
    if step == "owner":
        owner = payload.get("ownerKyc") or {}
        signatory = payload.get("signatory") or {}
        owner_name = (owner.get("name") or "").strip()
        return "owners", {
            "owner_name": owner_name or (signatory.get("name") or ""),
            "owner_dob": owner.get("dob") or signatory.get("dob") or "",
            "authorized_signatory": payload.get("authorisedSignatoryName") or signatory.get("name") or "",
            "designation": payload.get("signatoryRelation") or "",
            "owner_kyc": _person_kyc_to_storage(owner),
        }
    if step == "bank":
        bank = payload.get("bank") or {}
        return "bank", {
            "account_number": bank.get("accountNumber") or "",
            "ifsc": bank.get("ifsc") or "",
            "account_holder": bank.get("holderName") or "",
            "bank_name": bank.get("bankName") or "",
            "branch": bank.get("branch") or "",
            "account_type": bank.get("accountType") or "current",
            "penny_drop_status": bank.get("pennyDropStatus") or "idle",
        }
    if step == "documents":
        # The files themselves are Document rows; the step only records which
        # slots the merchant filled, so a reviewer can spot a missing upload.
        return "documents", {
            "acknowledged": True,
            "slots": [
                doc.get("slotId")
                for doc in payload.get("documents") or []
                if isinstance(doc, dict) and doc.get("slotId")
            ],
        }
    if step == "review":
        compliance = payload.get("compliance") or {}
        return "review", {
            "confirmed": bool(compliance.get("truthDeclaration")),
            "compliance": {
                key: bool(compliance.get(key))
                for key in (
                    "privacyPolicy",
                    "refundPolicy",
                    "terms",
                    "physicalAddress",
                    "authorisedDeclaration",
                    "truthDeclaration",
                    "dpdpConsent",
                )
            },
        }
    raise ValidationError(f"Unknown onboarding step: {step}")


def _agreement_embed(merchant: Merchant | None) -> dict:
    if merchant is None:
        return {
            "read": False,
            "authorised": False,
            "eSigned": False,
            "signerName": "",
            "adminSigned": False,
            "adminSignerName": "",
        }
    agreement = merchant.agreements.order_by("-created_at").first()
    if agreement is None:
        return {
            "read": False,
            "authorised": False,
            "eSigned": False,
            "signerName": "",
            "adminSigned": False,
            "adminSignerName": "",
        }
    merchant_signed = agreement.status in {
        Agreement.Status.MERCHANT_SIGNED,
        Agreement.Status.COUNTERSIGNED,
        Agreement.Status.EXECUTED,
    }
    admin_signed = agreement.status in {Agreement.Status.COUNTERSIGNED, Agreement.Status.EXECUTED}
    return {
        "read": True,
        "authorised": merchant_signed,
        "eSigned": merchant_signed,
        "signerName": agreement.signed_by.name if agreement.signed_by else "",
        "signedAt": agreement.merchant_signed_at.isoformat() if agreement.merchant_signed_at else None,
        "adminSigned": admin_signed,
        "adminSignerName": "Payswap",
        "adminSignedAt": agreement.countersigned_at.isoformat() if agreement.countersigned_at else None,
    }


def agreement_payload(agreement: Agreement) -> dict:
    return {
        "publicId": agreement.public_id,
        "status": agreement.status,
        "version": agreement.version,
        "body": agreement.body,
        "merchantSignedAt": agreement.merchant_signed_at.isoformat() if agreement.merchant_signed_at else None,
        "executedAt": agreement.executed_at.isoformat() if agreement.executed_at else None,
        "downloadUrl": f"/api/merchant/agreements/{agreement.public_id}/download/",
    }


def _order_status_to_angular(status: str) -> str:
    mapping = {
        OrderStatus.DRAFT: "draft",
        OrderStatus.SUBMITTED: "placed",
        OrderStatus.UNDER_REVIEW: "processing",
        OrderStatus.CHANGES_REQUESTED: "processing",
        OrderStatus.APPROVED: "fulfilled",
        OrderStatus.REJECTED: "cancelled",
        OrderStatus.CANCELLED: "cancelled",
    }
    return mapping.get(status, "draft")


def order_payload(order: PaymentOrder) -> dict:
    product = order.product
    brand = product.brand.name if product.brand_id else ""
    return {
        "id": order.public_id,
        "userId": order.merchant.owner.public_id,
        "kind": "brand_voucher",
        "title": product.name,
        "brand": brand,
        "quantity": order.quantity,
        "unitValue": float(order.unit_value),
        "amount": float(order.total),
        "status": _order_status_to_angular(order.status),
        "createdAt": order.created_at.isoformat(),
        "updatedAt": order.updated_at.isoformat(),
        "note": "",
        "mode": "live",
        "timeline": [
            {
                "status": _order_status_to_angular(order.status),
                "at": order.updated_at.isoformat(),
                "note": order.status.replace("_", " ").title(),
            }
        ],
        "invoiceId": order.public_id,
        "fulfilmentCodes": [],
        "legalName": order.merchant.business_name,
        "poNumber": order.public_id,
    }


def catalog_payload() -> list[dict]:
    rows = []
    for product in VoucherProduct.objects.filter(is_active=True, brand__is_active=True).select_related(
        "brand", "brand__service_type"
    ):
        brand = product.brand
        rows.append(
            {
                "id": str(product.pk),
                "brand": brand.name,
                "title": product.name,
                "kind": "brand_voucher",
                "denominations": [float(product.denomination)],
                "category": brand.service_type.name if brand.service_type_id else "Vouchers",
                "logo": "/branding/payswap-logo.png",
                "accent": "#1b4dfe",
                "productId": product.pk,
                "feeRate": float(product.fee_rate),
                "taxRate": float(product.tax_rate),
            }
        )
    return rows


def entity_type_for_registration(value: str) -> str:
    return _entity_type_from_angular(value or "individual")
