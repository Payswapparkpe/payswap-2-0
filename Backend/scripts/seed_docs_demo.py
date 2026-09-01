"""Seed a rich demo journey for role/flow documentation screenshots."""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from access.policy import Policy
from agreements.services import AgreementService
from catalog.models import VoucherProduct
from merchants.models import Merchant
from merchants.services import MerchantOnboardingService
from merchants.states import ApplicationStatus
from orders.models import OrderStatus
from orders.services import PaymentOrderService
from verification.models import Document
from verification.services import DocumentReviewService


PASSWORD = "CorrectHorse9!"
User = get_user_model()


def user(email: str) -> User:
    return User.objects.get(email=email)


def ensure_merchant() -> tuple[User, Merchant]:
    owner = user("merchant@payswap.local")
    owner.name = "Demo Merchant"
    owner.email_verified = True
    owner.mobile_verified = True
    owner.mobile = "9876543210"
    owner.save()
    application = MerchantOnboardingService.start(owner, entity_type=Merchant.EntityType.PRIVATE_LIMITED)
    merchant = application.merchant
    merchant.business_name = "Demo Retail Pvt Ltd"
    merchant.save(update_fields=["business_name", "updated_at"])

    MerchantOnboardingService.save_step(
        application,
        key="business",
        actor=owner,
        data={
            "legal_name": "Demo Retail Private Limited",
            "pan": "AABCD1234E",
            "gstin": "08AABCD1234E1Z5",
            "cin": "U72900RJ2020PTC123456",
            "registered_office": "Jaipur",
            "pincode": "302001",
            "trade_name": "Demo Retail",
        },
    )
    MerchantOnboardingService.save_step(
        application,
        key="owners",
        actor=owner,
        data={
            "owner_name": "Demo Merchant",
            "owner_dob": "1990-01-15",
            "authorized_signatory": "Demo Merchant",
        },
    )
    MerchantOnboardingService.save_step(
        application,
        key="bank",
        actor=owner,
        data={
            "account_holder": "Demo Retail Private Limited",
            "account_number": "123456789012",
            "ifsc": "HDFC0001234",
            "bank_name": "HDFC Bank",
        },
    )
    MerchantOnboardingService.save_step(
        application,
        key="documents",
        actor=owner,
        data={"confirmed": True},
    )
    MerchantOnboardingService.save_step(
        application,
        key="review",
        actor=owner,
        data={"accuracy_confirmed": True},
    )
    return owner, merchant


def ensure_document(merchant: Merchant, actor: User) -> Document:
    existing = merchant.documents.filter(doc_type=Document.DocType.PAN).first()
    if existing:
        return existing
    return DocumentReviewService.register_upload(
        merchant=merchant,
        actor=actor,
        doc_type=Document.DocType.PAN,
        uploaded_file=ContentFile(b"%PDF-1.4 demo pan", name="pan-demo.pdf"),
        document_number="AABCD1234E",
    )


def progress_to_commercial(owner: User, merchant: Merchant) -> None:
    admin = user("admin@payswap.local")
    kyc = user("kyc@payswap.local")
    application = merchant.applications.order_by("-created_at").first()

    document = ensure_document(merchant, owner)
    DocumentReviewService.approve(document=document, actor=kyc)

    if application.status in {ApplicationStatus.DRAFT, ApplicationStatus.CLARIFICATION_REQUIRED}:
        MerchantOnboardingService.submit(application, actor=owner)
    application.refresh_from_db()
    if application.status == ApplicationStatus.SUBMITTED:
        MerchantOnboardingService.start_review(application, actor=kyc)
    application.refresh_from_db()
    if application.status == ApplicationStatus.UNDER_REVIEW:
        try:
            MerchantOnboardingService.approve(application, actor=kyc)
        except Exception as exc:
            print("approve blocked:", exc)
            # Force commercial path for screenshots when evidence gates block.
            merchant.status = Merchant.Status.ACTIVE
            merchant.kyc_status = Merchant.VerificationState.VERIFIED
            merchant.kyb_status = Merchant.VerificationState.VERIFIED
            merchant.bank_status = Merchant.VerificationState.VERIFIED
            merchant.commercial_status = Merchant.CommercialStatus.INACTIVE
            merchant.save()

    merchant.refresh_from_db()
    if not merchant.agreements.exists():
        try:
            AgreementService.generate(merchant=merchant, actor=admin)
        except Exception as exc:
            print("agreement generate:", exc)
    agreement = merchant.agreements.order_by("-created_at").first()
    if agreement:
        try:
            if agreement.status in {"GENERATED", "INTERNAL_REVIEW", "MERCHANT_REVIEW"}:
                AgreementService.merchant_sign(agreement=agreement, actor=owner)
            agreement.refresh_from_db()
            if agreement.status == "MERCHANT_SIGNED":
                AgreementService.countersign(agreement=agreement, actor=admin)
        except Exception as exc:
            print("agreement sign path:", exc)
            merchant.agreement_status = Merchant.VerificationState.VERIFIED
            merchant.commercial_status = Merchant.CommercialStatus.ACTIVE
            merchant.save()

    merchant.refresh_from_db()
    if merchant.commercial_status != Merchant.CommercialStatus.ACTIVE:
        merchant.agreement_status = Merchant.VerificationState.VERIFIED
        merchant.commercial_status = Merchant.CommercialStatus.ACTIVE
        merchant.status = Merchant.Status.ACTIVE
        merchant.save()


def ensure_order(owner: User, merchant: Merchant):
    from orders.models import PaymentOrder

    existing = PaymentOrder.objects.filter(merchant=merchant).first()
    if existing:
        return existing
    product = VoucherProduct.objects.filter(is_active=True).select_related("brand").first()
    if not product:
        raise RuntimeError("No catalog product")
    order = PaymentOrderService.create(merchant=merchant, actor=owner, product=product, quantity=10)
    order = PaymentOrderService.submit(order, actor=owner)
    ops = user("ops@payswap.local")
    order = PaymentOrderService.transition(order, OrderStatus.UNDER_REVIEW, actor=ops)
    return order


def main():
    Policy.grant_role(user("admin@payswap.local"), "platform_admin")
    Policy.grant_role(user("kyc@payswap.local"), "kyc")
    Policy.grant_role(user("ops@payswap.local"), "operations")
    Policy.grant_role(user("merchant@payswap.local"), "merchant")

    owner, merchant = ensure_merchant()
    progress_to_commercial(owner, merchant)
    order = ensure_order(owner, merchant)
    merchant.refresh_from_db()
    print("merchant", merchant.public_id, merchant.status, merchant.commercial_status, merchant.agreement_status)
    print("application", merchant.applications.order_by("-created_at").first().status)
    print("agreements", list(merchant.agreements.values_list("public_id", "status")))
    print("order", order.public_id, order.status)
    print("docs", list(merchant.documents.values_list("public_id", "doc_type", "status")))


if __name__ == "__main__":
    main()
