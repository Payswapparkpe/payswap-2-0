"""Map Django domain objects to Angular console shapes."""

from django.conf import settings

from accounts.models import User
from agreements.models import Agreement
from catalog.models import VoucherProduct
from merchants.models import Merchant, OnboardingApplication
from merchants.privacy import decrypt_step_data
from merchants.states import ApplicationStatus, WIZARD_KEYS
from orders.models import OrderStatus, PaymentOrder


def user_payload(user: User) -> dict:
    return {
        "id": str(user.pk),
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
            return alias.get(key, "profile")
    return "review"


def onboarding_payload(*, user: User, application: OnboardingApplication | None, merchant: Merchant | None) -> dict:
    business = {}
    owners = {}
    bank = {}
    if application:
        for step in application.steps.all():
            data = decrypt_step_data(step.data)
            if step.key == "business":
                business = data
            elif step.key == "owners":
                owners = data
            elif step.key == "bank":
                bank = data

    documents = []
    if merchant:
        for doc in merchant.documents.all()[:50]:
            documents.append(
                {
                    "slotId": doc.doc_type.lower(),
                    "fileName": doc.file.name.rsplit("/", 1)[-1] if doc.file else doc.public_id,
                    "fileSize": doc.file.size if doc.file else 0,
                    "mimeType": "application/octet-stream",
                }
            )

    agreement = _agreement_embed(merchant)
    registered = _address_from_business(business)
    return {
        "userId": str(user.pk),
        "status": _account_status(application, merchant),
        "currentStep": _current_step(application),
        "profile": {
            "brandName": business.get("brand_name") or merchant.business_name if merchant else "",
            "legalName": business.get("legal_name") or (merchant.business_name if merchant else ""),
            "entityType": _entity_type_to_angular(merchant.entity_type if merchant else ""),
            "category": business.get("category") or "",
            "subCategory": business.get("sub_category") or "",
            "website": business.get("website") or "",
            "monthlyVolume": business.get("monthly_volume") or "",
            "gstin": business.get("gstin") or "",
            "noGstin": not bool(business.get("gstin")),
            "gstinOptions": [],
        },
        "identity": {
            "pan": business.get("pan") or "",
            "doi": business.get("doi") or "",
            "cin": business.get("cin") or "",
            "llpin": business.get("llpin") or "",
            "registeredAddress": registered,
            "operatingAddress": registered,
            "sameAsRegistered": True,
            "panCheck": None,
            "gstinCheck": None,
            "cinCheck": None,
            "gstinOptions": [],
        },
        "signatory": {
            "name": owners.get("owner_name") or owners.get("authorized_signatory") or user.name,
            "pan": business.get("pan") or "",
            "dob": owners.get("owner_dob") or "",
            "mobile": user.mobile or "",
            "path": "digilocker",
            "verified": bool(merchant and merchant.kyc_status == Merchant.VerificationState.VERIFIED),
            "digilockerFailed": False,
            "digilocker": None,
            "address": registered,
            "docs": [],
        },
        "kycPersonIsAuthorisedSignatory": True,
        "signatoryRelation": owners.get("designation") or "",
        "authorisedSignatoryName": owners.get("authorized_signatory") or "",
        "signatoryIsOwner": True,
        "ownerKyc": {
            "name": owners.get("owner_name") or "",
            "pan": business.get("pan") or "",
            "dob": owners.get("owner_dob") or "",
            "mobile": user.mobile or "",
            "path": "digilocker",
            "verified": False,
            "digilockerFailed": False,
            "digilocker": None,
            "address": registered,
            "docs": [],
        },
        "ubos": [],
        "ubosFrozen": False,
        "publicListedSkip": False,
        "bank": {
            "accountNumber": bank.get("account_number") or "",
            "ifsc": bank.get("ifsc") or "",
            "holderName": bank.get("account_holder") or "",
            "accountType": "current",
            "bankName": bank.get("bank_name") or "",
            "branch": bank.get("branch") or "",
            "pennyDropStatus": "matched"
            if merchant and merchant.bank_status == Merchant.VerificationState.VERIFIED
            else "idle",
        },
        "documents": documents,
        "compliance": {
            "privacyPolicy": True,
            "refundPolicy": True,
            "terms": True,
            "physicalAddress": bool(business.get("registered_office") or business.get("pincode")),
            "authorisedDeclaration": True,
            "truthDeclaration": True,
            "dpdpConsent": True,
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
        return "business", {
            "legal_name": profile.get("legalName") or profile.get("brandName") or "",
            "brand_name": profile.get("brandName") or "",
            "entity_type": profile.get("entityType") or "",
            "category": profile.get("category") or "",
            "sub_category": profile.get("subCategory") or "",
            "website": profile.get("website") or "",
            "monthly_volume": profile.get("monthlyVolume") or "",
            "gstin": profile.get("gstin") or "",
            "pan": identity.get("pan") or signatory.get("pan") or "",
            "doi": identity.get("doi") or "",
            "cin": identity.get("cin") or "",
            "llpin": identity.get("llpin") or "",
            "registered_office": registered.get("line1") or "",
            "pincode": registered.get("pin") or "",
            "city": registered.get("city") or "",
            "state": registered.get("state") or "",
        }
    if step in {"ubo", "owner"}:
        signatory = payload.get("signatory") or {}
        return "owners", {
            "owner_name": signatory.get("name") or "",
            "owner_dob": signatory.get("dob") or "",
            "authorized_signatory": payload.get("authorisedSignatoryName") or signatory.get("name") or "",
            "designation": payload.get("signatoryRelation") or "",
        }
    if step == "bank":
        bank = payload.get("bank") or {}
        return "bank", {
            "account_number": bank.get("accountNumber") or "",
            "ifsc": bank.get("ifsc") or "",
            "account_holder": bank.get("holderName") or "",
            "bank_name": bank.get("bankName") or "",
            "branch": bank.get("branch") or "",
        }
    if step == "documents":
        return "documents", {"acknowledged": True}
    if step == "review":
        compliance = payload.get("compliance") or {}
        return "review", {
            "confirmed": bool(compliance.get("truthDeclaration")),
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
        "userId": str(order.merchant.owner_id),
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
