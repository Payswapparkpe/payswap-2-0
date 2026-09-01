"""Adapter for the official ``cashfree-verification`` Python SDK.

Bank account sync and IFSC are not exposed by the SDK (as of 3.0.0); those
stay on the urllib client in ``integrations.cashfree``.
"""

from __future__ import annotations

import inspect
import json
import logging

from integrations.cashfree import CashfreeError

logger = logging.getLogger(__name__)


def _ensure_sdk_ssl_ca_bundle() -> None:
    """Point cashfree-verification urllib3 client at certifi CAs (macOS Python SSL)."""
    try:
        import certifi
        from cashfree_verification.configuration import Configuration

        if getattr(Configuration, "_payswap_certifi", False):
            return
        ca_path = certifi.where()
        _orig_init = Configuration.__init__

        def _init_with_certifi(self, *args, ssl_ca_cert=None, **kwargs):
            if ssl_ca_cert is None:
                ssl_ca_cert = ca_path
            _orig_init(self, *args, ssl_ca_cert=ssl_ca_cert, **kwargs)

        Configuration.__init__ = _init_with_certifi  # type: ignore[method-assign]
        Configuration._payswap_certifi = True
    except ImportError:
        logger.debug("certifi unavailable for cashfree sdk ssl", exc_info=True)


def _filter_kwargs(method, kwargs: dict) -> dict:
    try:
        allowed = set(inspect.signature(method).parameters)
        return {key: value for key, value in kwargs.items() if key in allowed}
    except (TypeError, ValueError):
        return kwargs


def _response_to_dict(response) -> dict:
    if response is None:
        return {}
    data = getattr(response, "data", response)
    if hasattr(data, "to_dict"):
        return data.to_dict()
    if isinstance(data, dict):
        return data
    return {}


def _map_api_exception(exc) -> CashfreeError:
    status = int(getattr(exc, "status", 0) or 0)
    body: dict = {}
    raw = getattr(exc, "body", None)
    if raw:
        try:
            body = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            body = {}
    message = str(body.get("message") or exc or "Cashfree error")
    code = str(body.get("code") or body.get("type") or "")
    retryable = status in {429, 500, 502, 503, 504}
    return CashfreeError(message, code=code, status=status, retryable=retryable)


class CashfreeSdkAdapter:
    """Thin wrapper around ``cashfree_verification`` with our error mapping."""

    def __init__(self, *, client_id: str, client_secret: str, environment: str = "sandbox"):
        _ensure_sdk_ssl_ca_bundle()
        from cashfree_verification.api_client import Cashfree as CfSdk

        self._api = CfSdk()
        CfSdk.XClientId = client_id
        CfSdk.XClientSecret = client_secret
        CfSdk.XEnvironment = CfSdk.SANDBOX if environment == "sandbox" else CfSdk.PRODUCTION
        self.client_id = client_id
        self.client_secret = client_secret
        self.environment = environment

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _signature_kwarg(self) -> dict:
        try:
            from django.conf import settings

            key_path = getattr(settings, "CASHFREE_PUBLIC_KEY_PATH", "") or ""
            if not key_path or not self.client_id:
                return {}
            from integrations.cashfree_signature import generate_cf_signature

            signature = generate_cf_signature(client_id=self.client_id, public_key_path=key_path)
            return {"x_cf_signature": signature} if signature else {}
        except Exception:
            logger.debug("cashfree sdk signature skipped", exc_info=True)
            return {}

    def _execute(self, method, *args, **kwargs) -> dict:
        if not self.configured:
            raise CashfreeError("Cashfree Verification is not configured.", code="not_configured")
        sig = self._signature_kwarg()
        if sig and "x_cf_signature" not in kwargs:
            kwargs.update(sig)
        kwargs = _filter_kwargs(method, kwargs)
        try:
            return _response_to_dict(method(*args, **kwargs))
        except CashfreeError:
            raise
        except Exception as exc:
            from cashfree_verification.exceptions import ApiException

            if isinstance(exc, ApiException):
                raise _map_api_exception(exc) from exc
            logger.warning("cashfree sdk transport error: %s", type(exc).__name__)
            raise CashfreeError(
                "The verification provider could not be reached.",
                code="transport_error",
                retryable=True,
            ) from exc

    def verify_pan_sync(self, *, pan: str, name: str = "") -> dict:
        from cashfree_verification.models.pan_request_schema import PanRequestSchema

        schema = PanRequestSchema(pan=pan, name=name or None)
        return self._execute(self._api.vrs_pan_verification, pan_request_schema=schema)

    def verify_pan_advance(self, *, verification_id: str, pan: str, name: str) -> dict:
        from cashfree_verification.models.pan_advance_request_schema import PanAdvanceRequestSchema

        schema = PanAdvanceRequestSchema(verification_id=verification_id, pan=pan, name=name)
        return self._execute(self._api.vrs_pan_advance_verification, pan_advance_request_schema=schema)

    def verify_gstin(self, *, gstin: str, business_name: str = "") -> dict:
        from cashfree_verification.models.gstin_request_schema import GstinRequestSchema

        schema = GstinRequestSchema(gstin=gstin, business_name=business_name or None)
        return self._execute(self._api.vrs_gstin_verification, gstin_request_schema=schema)

    def pan_to_gstin(self, *, verification_id: str, pan: str) -> dict:
        from cashfree_verification.models.pan_to_gstin_request_schema import PanToGstinRequestSchema

        schema = PanToGstinRequestSchema(verification_id=verification_id, pan=pan)
        return self._execute(self._api.vrs_pan_to_gstin_verification, pan_to_gstin_request_schema=schema)

    def verify_cin(self, *, verification_id: str, cin: str) -> dict:
        from cashfree_verification.models.cin_request_schema import CinRequestSchema

        schema = CinRequestSchema(verification_id=verification_id, cin=cin)
        return self._execute(self._api.vrs_cin_verification, cin_request_schema=schema)

    def digilocker_create_url(
        self, *, verification_id: str, documents: list[str], redirect_url: str, user_flow: str = "signup"
    ) -> dict:
        from cashfree_verification.models.digi_locker_verification_create_url_request_schema import (
            DigiLockerVerificationCreateUrlRequestSchema,
        )

        allowed = [doc for doc in documents if doc == "AADHAAR"] or ["AADHAAR"]
        schema = DigiLockerVerificationCreateUrlRequestSchema(
            verification_id=verification_id,
            document_requested=allowed,
            redirect_url=redirect_url,
        )
        return self._execute(
            self._api.vrs_digilocker_verification_create_url,
            digi_locker_verification_create_url_request_schema=schema,
        )

    def digilocker_get_status(self, *, verification_id: str = "", reference_id: str = "") -> dict:
        ref = int(reference_id) if reference_id and str(reference_id).isdigit() else None
        return self._execute(
            self._api.vrs_digilocker_verification_fetch_status,
            verification_id=verification_id or None,
            reference_id=ref,
        )

    def digilocker_get_document(
        self, *, document_type: str, verification_id: str = "", reference_id: str = ""
    ) -> dict:
        ref = int(reference_id) if reference_id and str(reference_id).isdigit() else None
        return self._execute(
            self._api.vrs_digilocker_verification_fetch_document,
            document_type=document_type,
            verification_id=verification_id or None,
            reference_id=ref,
        )

    def esign_upload_document(self, *, filename: str, content: bytes) -> dict:
        return self._execute(self._api.vrs_e_sign_upload_document, document=(filename, content))

    def esign_create_request(self, *, payload) -> dict:
        return self._execute(
            self._api.vrs_e_sign_create_signature,
            e_sign_verification_create_signature_request_schema=payload,
        )

    def esign_get_status(self, *, verification_id: str = "", reference_id: str = "") -> dict:
        ref = int(reference_id) if reference_id and str(reference_id).isdigit() else None
        return self._execute(
            self._api.vrs_e_sign_verification_fetch_status,
            verification_id=verification_id or None,
            reference_id=ref,
        )
