import re
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from access.policy import Policy
from audit.models import PublicIdSequence
from audit.services import AuditService
from notifications.services import NotificationService
from verification.models import BankAccount, Document

from .models import BeneficialOwner, Merchant, OnboardingApplication, OnboardingStep
from .privacy import decrypt_step_data, encrypt_step_data, merge_step_data
from .states import (
    ENTITY_BUSINESS_FIELDS,
    ONBOARDING_STEPS,
    REQUIRED_BEFORE_SUBMIT,
    ApplicationStatus,
    StepStatus,
)

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
CIN_RE = re.compile(r"^[A-Z][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
LLPIN_RE = re.compile(r"^[A-Z]{3}-[0-9]{4}$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


def _create_id_sequence(prefix: str, model, field: str) -> PublicIdSequence:
    baseline = 0
    marker = f"{prefix}-"
    for value in model.objects.values_list(field, flat=True).iterator():
        if not isinstance(value, str) or not value.startswith(marker):
            continue
        try:
            baseline = max(baseline, int(value[len(marker) :]))
        except ValueError:
            continue
    try:
        with transaction.atomic():
            return PublicIdSequence.objects.create(prefix=prefix, current=baseline)
    except IntegrityError:
        return PublicIdSequence.objects.select_for_update().get(prefix=prefix)


def next_public_id(prefix: str, model, field="public_id") -> str:
    """Race-safe sequential public IDs via a locked sequence row.

    The old max(public_id)+1 scheme collided under concurrency; a dedicated
    sequence row serializes allocation. Gaps from rolled-back transactions are
    acceptable — uniqueness and monotonicity are what matter.
    """
    with transaction.atomic():
        sequence = PublicIdSequence.objects.select_for_update().filter(prefix=prefix).first()
        if sequence is None:
            sequence = _create_id_sequence(prefix, model, field)
        sequence.current = F("current") + 1
        sequence.save(update_fields=["current"])
        sequence.refresh_from_db(fields=["current"])
        return f"{prefix}-{sequence.current:06d}"


class MerchantOnboardingService:
    @staticmethod
    @transaction.atomic
    def start(user, entity_type: str) -> OnboardingApplication:
        Policy.require(user, "portal.merchant")
        merchant, _ = Merchant.objects.get_or_create(
            owner=user,
            defaults={
                "public_id": next_public_id("PSM", Merchant),
                "entity_type": entity_type,
                "business_name": user.name or user.email,
            },
        )
        if merchant.entity_type != entity_type and merchant.status == Merchant.Status.DRAFT:
            merchant.entity_type = entity_type
            merchant.save(update_fields=["entity_type"])
        application = (
            merchant.applications.exclude(status=ApplicationStatus.REJECTED).order_by("-created_at").first()
        )
        if application is None:
            application = OnboardingApplication.objects.create(
                merchant=merchant,
                public_id=merchant.public_id,
                status=ApplicationStatus.DRAFT,
            )
            for position, (key, title) in enumerate(ONBOARDING_STEPS, start=1):
                status = StepStatus.COMPLETE if key == "account" else StepStatus.NOT_STARTED
                data = {"email": user.email, "mobile": user.mobile} if key == "account" else {}
                OnboardingStep.objects.create(
                    application=application,
                    key=key,
                    title=title,
                    position=position,
                    status=status,
                    data=data,
                )
        return application

    @staticmethod
    def seed_registered_address(application, *, address: str, pincode: str) -> None:
        step = application.steps.get(key="business")
        payload = merge_step_data(
            decrypt_step_data(step.data),
            {
                "registered_office": (address or "").strip(),
                "pincode": (pincode or "").strip(),
            },
        )
        step.data = encrypt_step_data(payload)
        step.save(update_fields=["data", "updated_at"])

    @staticmethod
    def _assert_transition(application, target):
        allowed = ApplicationStatus.TRANSITIONS.get(application.status, set())
        if target not in allowed:
            raise ValidationError(
                f"Application {application.public_id} cannot move from {application.status} to {target}."
            )

    @staticmethod
    def save_step(application, *, key, actor, data: dict) -> OnboardingStep:
        if application.merchant.owner_id != actor.id:
            raise PermissionDenied("You can only update your own application.")
        if application.status not in {
            ApplicationStatus.DRAFT,
            ApplicationStatus.CLARIFICATION_REQUIRED,
        }:
            raise ValidationError("This application cannot be edited in its current state.")
        step = application.steps.get(key=key)
        data = merge_step_data(decrypt_step_data(step.data), dict(data))
        if key == "business":
            MerchantOnboardingService._validate_business(application.merchant.entity_type, data)
            application.merchant.business_name = data.get("legal_name", application.merchant.business_name)
            application.merchant.save(update_fields=["business_name"])
        if key == "owners":
            MerchantOnboardingService._validate_owners(data)
            MerchantOnboardingService._sync_beneficial_owners(application.merchant, data)
        if key == "bank":
            ifsc = (data.get("ifsc") or "").upper()
            if ifsc and not IFSC_RE.match(ifsc):
                raise ValidationError("Enter a valid IFSC.")
            data["ifsc"] = ifsc
            account_number = "".join(ch for ch in (data.get("account_number") or "") if ch.isdigit())
            if account_number:
                MerchantOnboardingService._persist_bank_account(
                    application.merchant,
                    holder=data.get("account_holder") or application.merchant.business_name,
                    ifsc=ifsc,
                    account_number=account_number,
                )
                data["account_number"] = f"****{account_number[-4:]}"
                data["account_last4"] = account_number[-4:]
        step.data = encrypt_step_data(data)
        step.status = StepStatus.COMPLETE
        step.clarification_message = ""
        step.save(update_fields=["data", "status", "clarification_message", "updated_at"])
        if key == "business":
            MerchantOnboardingService._mirror_identity_steps(application, data)
        return step

    @staticmethod
    def _validate_business(entity_type, data):
        required = ENTITY_BUSINESS_FIELDS.get(entity_type, ["legal_name"])
        missing = [field for field in required if not (data.get(field) or "").strip()]
        if missing:
            raise ValidationError("Complete the required business details.")
        pan = (data.get("pan") or "").upper()
        if pan and not PAN_RE.match(pan):
            raise ValidationError("Enter a valid PAN.")
        gstin = (data.get("gstin") or "").upper()
        if gstin and not GSTIN_RE.match(gstin):
            raise ValidationError("Enter a valid GSTIN.")
        pincode = (data.get("pincode") or "").strip()
        if pincode and not re.fullmatch(r"[1-9][0-9]{5}", pincode):
            raise ValidationError("Enter a valid PIN code.")
        cin = (data.get("cin") or "").upper()
        if cin and not CIN_RE.match(cin):
            raise ValidationError("Enter a valid CIN.")
        llpin = (data.get("llpin") or "").upper()
        if llpin and not LLPIN_RE.match(llpin):
            raise ValidationError("Enter a valid LLPIN.")

    @staticmethod
    def _validate_owners(data):
        if not (data.get("owner_name") or data.get("authorized_signatory") or "").strip():
            raise ValidationError("Add at least one owner.")
        aadhaar = "".join(ch for ch in (data.get("aadhaar") or "") if ch.isdigit())
        if aadhaar:
            if not re.fullmatch(r"[2-9][0-9]{11}", aadhaar):
                raise ValidationError("Enter a valid Aadhaar number.")
            data["aadhaar"] = aadhaar
        dob = (data.get("owner_dob") or "").strip()
        if dob and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dob):
            raise ValidationError("Enter a valid date of birth.")
        if not (data.get("authorized_signatory") or "").strip():
            data["authorized_signatory"] = (data.get("owner_name") or "").strip()

    @staticmethod
    def _mirror_identity_steps(application, business_data):
        """Copy PAN/GSTIN/CIN into hidden KYC/KYB steps so they are not re-asked."""
        copies = {
            "kyc": {"pan": business_data.get("pan", "")},
            "kyb": {
                "gstin": business_data.get("gstin", ""),
                "cin": business_data.get("cin") or business_data.get("llpin") or "",
            },
        }
        for key, payload in copies.items():
            sibling = application.steps.filter(key=key).first()
            if sibling is None:
                continue
            sibling.data = encrypt_step_data(payload)
            sibling.status = StepStatus.COMPLETE
            sibling.clarification_message = ""
            sibling.save(update_fields=["data", "status", "clarification_message", "updated_at"])

    @staticmethod
    def _persist_bank_account(merchant, *, holder, ifsc, account_number):
        account, _created = BankAccount.objects.get_or_create(
            merchant=merchant,
            defaults={
                "account_holder": holder or "",
                "ifsc": ifsc,
                "account_number_encrypted": "",
            },
        )
        if account.verified:
            return
        account.account_holder = holder or account.account_holder
        account.ifsc = ifsc
        account.set_account_number(account_number)
        account.save()

    @staticmethod
    def _sync_beneficial_owners(merchant, data):
        people = list(data.get("people") or [])
        if not people:
            name = (data.get("owner_name") or data.get("authorized_signatory") or "").strip()
            if name:
                people = [
                    {
                        "name": name,
                        "designation": data.get("designation") or "",
                        "percent": data.get("ownership_percent") or "",
                        "signatory": True,
                    }
                ]
        merchant.owners.all().delete()
        signatory_name = (data.get("authorized_signatory") or "").strip()
        for person in people:
            name = (person.get("name") or "").strip()
            if not name:
                continue
            percent = person.get("percent") or person.get("ownership_percent")
            try:
                percent_value = Decimal(str(percent)) if percent not in (None, "") else None
            except (InvalidOperation, TypeError, ValueError):
                percent_value = None
            BeneficialOwner.objects.create(
                merchant=merchant,
                full_name=name,
                role=person.get("designation") or "",
                ownership_percent=percent_value,
                is_authorized_signatory=bool(
                    person.get("signatory") or name.casefold() == signatory_name.casefold()
                ),
            )

    @staticmethod
    @transaction.atomic
    def submit(application, *, actor, confirmed=True, request=None) -> OnboardingApplication:
        if application.merchant.owner_id != actor.id:
            raise PermissionDenied("You can only submit your own application.")
        if not confirmed:
            raise ValidationError(
                "Confirm that the information provided is accurate and belongs to the business represented."
            )
        business = application.steps.filter(key="business").first()
        if business and business.status == StepStatus.COMPLETE:
            MerchantOnboardingService._mirror_identity_steps(application, decrypt_step_data(business.data))
        incomplete = application.steps.filter(key__in=REQUIRED_BEFORE_SUBMIT).exclude(
            status=StepStatus.COMPLETE
        )
        if incomplete.exists():
            raise ValidationError("Complete every required section before submitting for verification.")
        MerchantOnboardingService._assert_transition(application, ApplicationStatus.SUBMITTED)
        application.status = ApplicationStatus.SUBMITTED
        application.submitted_at = timezone.now()
        application.save(update_fields=["status", "submitted_at"])
        application.merchant.status = Merchant.Status.PENDING_REVIEW
        application.merchant.save(update_fields=["status"])
        AuditService.record(
            actor=actor,
            action="onboarding.submit",
            resource_type="application",
            resource_id=application.public_id,
            request=request,
        )
        return application

    @staticmethod
    def start_review(application, *, actor, request=None) -> OnboardingApplication:
        Policy.require(actor, "merchant.review", application.merchant)
        MerchantOnboardingService._assert_transition(application, ApplicationStatus.UNDER_REVIEW)
        application.status = ApplicationStatus.UNDER_REVIEW
        application.reviewed_by = actor
        application.save(update_fields=["status", "reviewed_by"])
        AuditService.record(
            actor=actor,
            action="onboarding.start_review",
            resource_type="application",
            resource_id=application.public_id,
            request=request,
        )
        return application

    @staticmethod
    def request_clarification(
        application, *, actor, step_key, message, request=None
    ) -> OnboardingApplication:
        Policy.require(actor, "merchant.review", application.merchant)
        MerchantOnboardingService._assert_transition(application, ApplicationStatus.CLARIFICATION_REQUIRED)
        step = application.steps.get(key=step_key)
        step.status = StepStatus.NEEDS_CORRECTION
        step.clarification_message = message
        step.save(update_fields=["status", "clarification_message"])
        application.status = ApplicationStatus.CLARIFICATION_REQUIRED
        application.save(update_fields=["status"])
        application.merchant.bank_status = (
            Merchant.VerificationState.ACTION_REQUIRED
            if step_key == "bank"
            else application.merchant.bank_status
        )
        application.merchant.save(update_fields=["bank_status"])
        NotificationService.notify(
            user=application.merchant.owner,
            title="Action required",
            body="Please update the highlighted section of your merchant application.",
            url=f"/merchant/onboarding/{application.public_id}/",
            email=True,
            template="onboarding_clarification",
            context={"reference": application.public_id, "reason": message},
        )
        AuditService.record(
            actor=actor,
            action="onboarding.clarification",
            resource_type="application",
            resource_id=application.public_id,
            reason=message,
            request=request,
        )
        return application

    @staticmethod
    def reject(application, *, actor, reason, notes="", request=None) -> OnboardingApplication:
        Policy.require(actor, "merchant.review", application.merchant)
        MerchantOnboardingService._assert_transition(application, ApplicationStatus.REJECTED)
        application.status = ApplicationStatus.REJECTED
        application.rejection_reason = reason
        application.rejection_notes = notes
        application.save(update_fields=["status", "rejection_reason", "rejection_notes"])
        application.merchant.status = Merchant.Status.REJECTED
        application.merchant.save(update_fields=["status"])
        NotificationService.notify(
            user=application.merchant.owner,
            title="Application not approved",
            body="Your merchant application was not approved.",
            url="/merchant/",
            email=True,
            template="application_rejected",
            context={"reference": application.public_id, "reason": reason},
        )
        AuditService.record(
            actor=actor,
            action="onboarding.reject",
            resource_type="application",
            resource_id=application.public_id,
            reason=reason,
            request=request,
        )
        return application

    @staticmethod
    def approval_blockers(application) -> list[str]:
        """Evidence required before an application may be approved.

        Approval flips KYC/KYB/bank to VERIFIED, so it must not succeed while
        the merchant's latest documents are unreviewed or rejected. The latest
        upload per document type is authoritative, so a rejected file stops
        blocking once a replacement is verified.
        """
        blockers: list[str] = []
        latest: dict[str, Document] = {}
        for document in application.merchant.documents.all():
            latest.setdefault(document.doc_type, document)
        pan = latest.get(Document.DocType.PAN)
        if pan is None:
            blockers.append("Upload the merchant's PAN card document and verify it before approval.")
        for document in latest.values():
            label = document.get_doc_type_display()
            if document.status in {
                Document.Status.UPLOADED,
                Document.Status.UNDER_REVIEW,
                Document.Status.ACTION_REQUIRED,
            }:
                blockers.append(f"{label} is still awaiting document review.")
            elif document.status == Document.Status.REJECTED:
                blockers.append(f"{label} was rejected; verify a replacement before approval.")
        return blockers

    @staticmethod
    def approve(application, *, actor, request=None) -> OnboardingApplication:
        Policy.require(actor, "merchant.review", application.merchant)
        MerchantOnboardingService._assert_transition(application, ApplicationStatus.APPROVED)
        blockers = MerchantOnboardingService.approval_blockers(application)
        if blockers:
            # Recorded outside the mutation transaction so the failure audit
            # is not rolled back together with the rejected state change.
            reason = " ".join(blockers)
            AuditService.record(
                actor=actor,
                action="merchant.approve",
                resource_type="merchant",
                resource_id=application.merchant.public_id,
                result="failure",
                reason=reason,
                request=request,
            )
            raise ValidationError(reason)
        with transaction.atomic():
            application.status = ApplicationStatus.APPROVED
            application.save(update_fields=["status"])
            merchant = application.merchant
            merchant.status = Merchant.Status.ACTIVE
            merchant.kyc_status = Merchant.VerificationState.VERIFIED
            merchant.kyb_status = Merchant.VerificationState.VERIFIED
            merchant.bank_status = Merchant.VerificationState.VERIFIED
            merchant.save(update_fields=["status", "kyc_status", "kyb_status", "bank_status"])
            AuditService.record(
                actor=actor,
                action="merchant.approve",
                resource_type="merchant",
                resource_id=merchant.public_id,
                after={"status": merchant.status},
                request=request,
            )
        # Deferred: agreements.services imports merchants.services.next_public_id.
        from agreements.services import AgreementService

        AgreementService.issue_if_verification_complete(merchant=merchant, actor=actor, request=request)
        NotificationService.notify(
            user=merchant.owner,
            title="Application approved",
            body="Your merchant application has been approved. Review the prefilled agreement and complete Aadhaar eSign.",
            url="/merchant/agreements/",
            email=True,
            template="application_approved",
            context={"reference": merchant.public_id},
        )
        return application
