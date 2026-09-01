"""Unified Cashfree Secure ID verification API for the partner console."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from merchants.privacy import decrypt_step_data
from verification.alignment import evaluate_alignment
from verification.digilocker import DigiLockerService
from verification.services import VerificationService

from .mixins import JsonView, MerchantRequiredMixin, api_error, parse_json
from .onboarding import _merchant_context


def _verification_status(merchant, application=None):
    alignment = evaluate_alignment(merchant=merchant, application=application)
    return {
        "kycStatus": merchant.kyc_status,
        "kybStatus": merchant.kyb_status,
        "bankStatus": merchant.bank_status,
        "agreementStatus": merchant.agreement_status,
        "commercialStatus": merchant.commercial_status,
        "nameAlignment": alignment,
    }


class VerificationView(MerchantRequiredMixin, JsonView):
    """Single entry point for Cashfree verification actions from Angular."""

    @method_decorator(ratelimit(key="user_or_ip", rate="60/m", method="POST", block=True))
    def post(self, request):
        body = parse_json(request)
        action = (body.get("action") or "start").lower()
        kind = (body.get("kind") or "").lower()
        merchant, application = _merchant_context(request.user)

        if action == "check":
            return self._check(kind, body, merchant=merchant, application=application, request=request)
        if action == "start":
            return self._start(kind, body, merchant=merchant, application=application, request=request)
        if action == "sync":
            return self._sync(kind, body, merchant=merchant, request=request)
        if action == "validate":
            return self._validate(kind, merchant=merchant, application=application)
        return api_error("Unsupported verification action.")

    def get(self, request):
        merchant, application = _merchant_context(request.user)
        return self.ok(_verification_status(merchant, application))

    def _check(self, kind, body, *, merchant, application, request):
        if kind == "pan":
            return self.ok(
                VerificationService.preview_pan(
                    merchant=merchant,
                    actor=request.user,
                    pan=body.get("pan") or "",
                    name=body.get("name") or "",
                    request=request,
                )
            )
        if kind == "gstin":
            return self.ok(
                VerificationService.preview_gstin(
                    merchant=merchant,
                    actor=request.user,
                    gstin=body.get("gstin") or "",
                    request=request,
                )
            )
        if kind == "cin":
            return self.ok(
                VerificationService.preview_cin(
                    merchant=merchant,
                    actor=request.user,
                    cin=body.get("cin") or "",
                    request=request,
                )
            )
        if kind == "udyam":
            return self.ok(
                VerificationService.preview_udyam(
                    merchant=merchant,
                    actor=request.user,
                    udyam=body.get("udyam") or body.get("udyamNumber") or "",
                    owner_name=body.get("ownerName") or body.get("name") or merchant.business_name or "",
                    request=request,
                )
            )
        if kind == "pan_gstin_list":
            return self.ok(
                VerificationService.preview_pan_gstin_list(
                    merchant=merchant,
                    actor=request.user,
                    pan=body.get("pan") or "",
                    request=request,
                )
            )
        if kind == "ifsc":
            return self._check_ifsc(body, merchant=merchant, request=request)
        if kind == "bank":
            return self.ok(
                VerificationService.preview_bank(
                    merchant=merchant,
                    actor=request.user,
                    account_number=body.get("accountNumber") or "",
                    ifsc=body.get("ifsc") or "",
                    name=body.get("name") or body.get("holderName") or merchant.business_name,
                    request=request,
                )
            )
        if kind == "digilocker_account":
            pan = (body.get("pan") or "").upper().strip()
            if getattr(settings, "AUTH_TEST_MODE", False) and pan.endswith("9"):
                return self.ok(
                    {
                        "verificationId": "",
                        "referenceId": 0,
                        "mobile": body.get("mobile") or "",
                        "status": "ACCOUNT_NOT_FOUND",
                    }
                )
            return self.ok(
                {
                    "verificationId": "",
                    "referenceId": 0,
                    "mobile": body.get("mobile") or "",
                    "status": "ACCOUNT_EXISTS",
                }
            )
        return api_error("Unsupported verification kind for check.")

    def _start(self, kind, body, *, merchant, application, request):
        if kind == "pan":
            business = application.steps.get(key="business")
            owners = decrypt_step_data(application.steps.get(key="owners").data)
            data = decrypt_step_data(business.data)
            record = VerificationService.verify_pan(
                merchant=merchant,
                actor=request.user,
                pan=body.get("pan") or data.get("pan") or "",
                name=body.get("name") or owners.get("owner_name") or request.user.name,
                dob=body.get("dob") or owners.get("owner_dob") or "",
                request=request,
            )
            return self.ok({"publicId": record.public_id, "status": record.status})
        if kind == "gstin":
            record = VerificationService.verify_gstin(
                merchant=merchant,
                actor=request.user,
                gstin=body.get("gstin") or "",
                request=request,
            )
            return self.ok({"publicId": record.public_id, "status": record.status})
        if kind == "bank":
            record = VerificationService.verify_bank(
                merchant=merchant,
                actor=request.user,
                account_number=body.get("accountNumber") or "",
                ifsc=body.get("ifsc") or "",
                name=body.get("name") or merchant.business_name,
                request=request,
            )
            return self.ok({"publicId": record.public_id, "status": record.status})
        if kind in {"aadhaar", "digilocker"}:
            if body.get("aadhaar") or body.get("aadhaarNumber"):
                url = DigiLockerService.start_aadhaar(
                    merchant=merchant,
                    actor=request.user,
                    aadhaar_number=body.get("aadhaar") or body.get("aadhaarNumber") or "",
                    request=request,
                )
                return self.ok({"redirectUrl": url, "status": "PENDING"})
            payload = DigiLockerService.start_kyc(
                merchant=merchant,
                actor=request.user,
                request=request,
                redirect_url=body.get("redirectUrl") or "",
            )
            return self.ok(payload)
        if kind == "collected":
            records = VerificationService.verify_collected(
                merchant=merchant, actor=request.user, request=request
            )
            return self.ok({"records": [{"publicId": r.public_id, "status": r.status} for r in records]})
        return api_error("Unsupported verification kind.")

    def _sync(self, kind, body, *, merchant, request):
        if kind not in {"aadhaar", "digilocker"}:
            return api_error("Unsupported verification kind for sync.")
        verification_id = body.get("verificationId") or ""
        record = merchant.verification_records.filter(verification_id=verification_id).first()
        if record is None:
            return api_error("Verification session not found.")
        return self.ok(DigiLockerService.digilocker_status_payload(record=record))

    def _validate(self, kind, *, merchant, application):
        if kind == "alignment":
            return self.ok(evaluate_alignment(merchant=merchant, application=application))
        return api_error("Unsupported validation kind.")

    def _check_ifsc(self, body, *, merchant, request):
        record = VerificationService.verify_ifsc(
            merchant=merchant,
            actor=request.user,
            ifsc=body.get("ifsc") or "",
            request=request,
        )
        verified_data = {}
        if record.verified_data_encrypted:
            import json

            from core.crypto import decrypt_text

            try:
                verified_data = json.loads(decrypt_text(record.verified_data_encrypted))
            except (json.JSONDecodeError, TypeError):
                verified_data = {}
        return self.ok(
            {
                "ifsc": record.document_masked,
                "bankName": str(verified_data.get("bank") or ""),
                "branch": str(verified_data.get("branch") or verified_data.get("address") or ""),
                "status": record.status,
                "referenceId": int(record.reference_id or 0),
                "verificationId": record.verification_id,
            }
        )


class VerificationStartView(MerchantRequiredMixin, JsonView):
    """Backward-compatible alias for ``POST /verification/start``."""

    def post(self, request):
        body = parse_json(request)
        merchant, application = _merchant_context(request.user)
        view = VerificationView()
        return view._start(
            (body.get("kind") or "").lower(),
            body,
            merchant=merchant,
            application=application,
            request=request,
        )


class VerificationStatusView(MerchantRequiredMixin, JsonView):
    def get(self, request):
        merchant, application = _merchant_context(request.user)
        return self.ok(_verification_status(merchant, application))
