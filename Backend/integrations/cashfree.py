"""Cashfree Secure ID (Verification Suite) client.

Verified against the official API reference (x-api-version 2024-12-01) on
17 Aug 2026 — see docs/cashfree-verification-plan.md for the endpoint table.

Contract rules honoured here:
- every V2 operation carries our caller-generated ``verification_id`` so the
  provider can dedupe retries (409 on duplicates) and we can correlate events;
- retries only happen when an idempotency key was supplied or the operation is
  a read — never blind retries on non-idempotent calls;
- error bodies map to a structured CashfreeError (code/type/http status);
- no credential material is ever logged or returned.
"""

import logging
import time
import urllib.error
import uuid

from .http import UrllibHttp

logger = logging.getLogger(__name__)

SANDBOX_BASE = "https://sandbox.cashfree.com/verification"
PRODUCTION_BASE = "https://api.cashfree.com/verification"
API_VERSION = "2024-12-01"

RETRYABLE_HTTP = {429, 500, 502, 503, 504}
RETRY_DELAYS = (0.5, 1.5)


class CashfreeError(Exception):
    def __init__(self, message: str, *, code: str = "", status: int = 0, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable


def new_verification_id(prefix: str) -> str:
    """Provider-safe idempotency key: alphanumeric + hyphen, max 50 chars."""
    return f"{prefix}-{uuid.uuid4().hex[:24]}"[:50]


class CashfreeClient:
    def __init__(
        self,
        *,
        client_id,
        client_secret,
        environment="sandbox",
        http=None,
        sleeper=time.sleep,
        sdk=None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.environment = environment
        self.http = http or UrllibHttp()
        self.sleeper = sleeper
        self.base_url = PRODUCTION_BASE if environment == "production" else SANDBOX_BASE
        if sdk is not None:
            self._sdk = sdk
        elif http is None:
            from integrations.cashfree_sdk import CashfreeSdkAdapter

            self._sdk = CashfreeSdkAdapter(
                client_id=client_id,
                client_secret=client_secret,
                environment=environment,
            )
        else:
            self._sdk = None

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _headers(self):
        headers = {
            "x-client-id": self.client_id,
            "x-client-secret": self.client_secret,
            "x-api-version": API_VERSION,
        }
        try:
            from django.conf import settings

            key_path = getattr(settings, "CASHFREE_PUBLIC_KEY_PATH", "") or ""
            if key_path and self.client_id:
                from integrations.cashfree_signature import generate_cf_signature

                signature = generate_cf_signature(client_id=self.client_id, public_key_path=key_path)
                if signature:
                    headers["x-cf-signature"] = signature
        except Exception:
            logger.debug("cashfree signature header skipped", exc_info=True)
        return headers

    def _request(self, method, path, *, payload=None, files=None, params=None, idempotent=False):
        if not self.configured:
            raise CashfreeError("Cashfree Verification is not configured.", code="not_configured")
        url = f"{self.base_url}{path}"
        attempts = 1 + (len(RETRY_DELAYS) if idempotent else 0)
        last_error = None
        for attempt in range(attempts):
            if attempt:
                self.sleeper(RETRY_DELAYS[attempt - 1])
            try:
                if method == "GET":
                    status, data = self.http.get_json(url, headers=self._headers(), params=params, timeout=20)
                elif files:
                    status, data = self.http.json_request(
                        method, url, headers=self._headers(), files=files, timeout=60
                    )
                else:
                    status, data = self.http.json_request(
                        method, url, headers=self._headers(), json=payload, timeout=30
                    )
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = CashfreeError(
                    "The verification provider could not be reached.",
                    code="transport_error",
                    retryable=True,
                )
                logger.warning(
                    "cashfree transport error on %s (attempt %d): %s", path, attempt + 1, type(exc).__name__
                )
                continue
            if status < 400:
                return data
            code = str(data.get("code") or "")
            message = data.get("message") or f"Cashfree error {status}"
            retryable = status in RETRYABLE_HTTP
            if not retryable or attempt == attempts - 1:
                raise CashfreeError(message, code=code, status=status, retryable=retryable)
            logger.warning(
                "cashfree retryable error on %s (attempt %d): http=%d code=%s",
                path,
                attempt + 1,
                status,
                code,
            )
        raise last_error or CashfreeError(
            "The verification provider could not be reached.", code="transport_error", retryable=True
        )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    def verify_pan_lite(self, *, verification_id: str, pan: str, name: str, dob: str) -> dict:
        """POST /pan-lite — dob must be YYYY-MM-DD as per PAN records."""
        return self._request(
            "POST",
            "/pan-lite",
            payload={"verification_id": verification_id, "pan": pan, "name": name, "dob": dob},
            idempotent=True,
        )

    def verify_pan_sync(self, *, pan: str, name: str = "") -> dict:
        """Verify PAN via the official SDK (registry / KYB preview)."""
        if self._sdk:
            return self._sdk.verify_pan_sync(pan=pan, name=name)
        raise CashfreeError("Cashfree Verification SDK is not available.", code="not_configured")

    def verify_pan_360(self, *, verification_id: str, pan: str, name: str = "") -> dict:
        """PAN 360 — richer entity / individual details from Cashfree."""
        if self._sdk:
            return self._sdk.verify_pan_advance(
                verification_id=verification_id, pan=pan, name=(name or "").strip()
            )
        raise CashfreeError("Cashfree Verification SDK is not available.", code="not_configured")

    def pan_to_gstin(self, *, verification_id: str, pan: str) -> dict:
        if self._sdk:
            return self._sdk.pan_to_gstin(verification_id=verification_id, pan=pan)
        raise CashfreeError("Cashfree Verification SDK is not available.", code="not_configured")

    def verify_cin(self, *, verification_id: str, cin: str) -> dict:
        if self._sdk:
            return self._sdk.verify_cin(verification_id=verification_id, cin=cin)
        raise CashfreeError("Cashfree Verification SDK is not available.", code="not_configured")

    def verify_gstin(self, *, gstin: str) -> dict:
        """POST /gstin — no caller verification_id in the schema; never retried."""
        if self._sdk:
            return self._sdk.verify_gstin(gstin=gstin)
        return self._request("POST", "/gstin", payload={"gstin": gstin})

    def verify_udyam(self, *, verification_id: str, udyam: str) -> dict:
        """POST /udyam — MSME registration verification."""
        return self._request(
            "POST",
            "/udyam",
            payload={"verification_id": verification_id, "udyam": udyam},
            idempotent=True,
        )

    # ------------------------------------------------------------------
    # Banking
    # ------------------------------------------------------------------
    def verify_bank_sync(self, *, bank_account: str, ifsc: str, name: str = "", phone: str = "") -> dict:
        """POST /bank-account/sync — no caller verification_id in the schema."""
        payload = {"bank_account": bank_account, "ifsc": ifsc}
        if name:
            payload["name"] = name
        if phone:
            payload["phone"] = phone
        return self._request("POST", "/bank-account/sync", payload=payload)

    def verify_ifsc(self, *, verification_id: str, ifsc: str) -> dict:
        return self._request(
            "POST",
            "/ifsc",
            payload={"verification_id": verification_id, "ifsc": ifsc},
            idempotent=True,
        )

    # ------------------------------------------------------------------
    # DigiLocker (current Aadhaar verification path; OTP Aadhaar is discontinued)
    # ------------------------------------------------------------------
    def digilocker_create_url(
        self, *, verification_id: str, documents: list[str], redirect_url: str, user_flow: str = "signup"
    ) -> dict:
        if self._sdk:
            return self._sdk.digilocker_create_url(
                verification_id=verification_id,
                documents=documents,
                redirect_url=redirect_url,
                user_flow=user_flow,
            )
        return self._request(
            "POST",
            "/digilocker",
            payload={
                "verification_id": verification_id,
                "document_requested": documents,
                "redirect_url": redirect_url,
                "user_flow": user_flow,
            },
            idempotent=True,
        )

    def digilocker_get_status(self, *, verification_id: str = "", reference_id: str = "") -> dict:
        if self._sdk:
            return self._sdk.digilocker_get_status(
                verification_id=verification_id, reference_id=reference_id
            )
        params = {}
        if verification_id:
            params["verification_id"] = verification_id
        elif reference_id:
            params["reference_id"] = reference_id
        return self._request("GET", "/digilocker", params=params, idempotent=True)

    def digilocker_get_document(
        self, *, document_type: str, verification_id: str = "", reference_id: str = ""
    ) -> dict:
        if self._sdk:
            return self._sdk.digilocker_get_document(
                document_type=document_type,
                verification_id=verification_id,
                reference_id=reference_id,
            )
        params = {}
        if verification_id:
            params["verification_id"] = verification_id
        elif reference_id:
            params["reference_id"] = reference_id
        return self._request("GET", f"/digilocker/document/{document_type}", params=params, idempotent=True)

    # ------------------------------------------------------------------
    # Aadhaar eSign
    # ------------------------------------------------------------------
    def esign_upload_document(self, *, filename: str, content: bytes) -> dict:
        """POST /esignature/document — multipart PDF, max 10MB."""
        return self._request(
            "POST",
            "/esignature/document",
            files={"document": (filename, content, "application/pdf")},
        )

    def esign_create_request(
        self,
        *,
        verification_id: str,
        document_id: int,
        signer_name: str,
        signer_email: str,
        signer_phone: str = "",
        expiry_in_days: int = 7,
        notify: bool = True,
        sign_positions: list[dict] | None = None,
    ) -> dict:
        signer = {"name": signer_name, "email": signer_email, "sequence": 1}
        if signer_phone:
            signer["phone"] = signer_phone
        if sign_positions:
            signer["sign_positions"] = sign_positions
        return self._request(
            "POST",
            "/esignature",
            payload={
                "verification_id": verification_id,
                "document_id": document_id,
                "notification_modes": ["email"] if notify else [],
                "auth_type": "AADHAAR",
                "expiry_in_days": str(min(expiry_in_days, 15)),
                "signers": [signer],
            },
            idempotent=True,
        )

    def esign_get_status(self, *, verification_id: str = "", reference_id: str = "") -> dict:
        params = {}
        if verification_id:
            params["verification_id"] = verification_id
        elif reference_id:
            params["reference_id"] = reference_id
        return self._request("GET", "/esignature", params=params, idempotent=True)

    def download_signed_document(self, url: str) -> bytes:
        return self.http.download(url, timeout=60)
