"""Inbound webhook receiver for Cashfree Secure ID (eSign + DigiLocker).

Security model per the official docs (verified 17 Aug 2026): the signature is
``base64(HMAC-SHA256(secret, x-webhook-timestamp + raw_body))`` — timestamp and
raw body concatenated with no separator. ``x-webhook-timestamp`` may be seconds
or milliseconds; both are accepted within a 5-minute replay tolerance. CSRF is
exempt because no session or cookie is involved; the signature is the credential.

Routing: ``E_SIGN_*`` events drive the agreement eSign lifecycle and
``DIGILOCKER_*`` events drive Aadhaar verification. Every event is deduplicated
by event id. Payment events are ignored (payments are out of product scope).
"""

import base64
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

from agreements.esign import HANDLED_EVENTS as ESIGN_HANDLED_EVENTS
from agreements.esign import EsignStatusService
from audit.models import WebhookEvent
from verification.digilocker import HANDLED_EVENTS as DIGILOCKER_HANDLED_EVENTS
from verification.digilocker import DigiLockerService

logger = logging.getLogger("payswap.webhooks")

TIMESTAMP_TOLERANCE_SECONDS = 300


def _expected_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    digest = hmac.new(secret.encode(), timestamp.encode() + raw_body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _signature_ok(*, secret: str, timestamp: str, signature: str, raw_body: bytes) -> bool:
    if not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if ts > 10_000_000_000:  # milliseconds epoch (Cashfree sends ms)
        ts //= 1000
    if abs(int(timezone.now().timestamp()) - ts) > TIMESTAMP_TOLERANCE_SECONDS:
        return False
    return hmac.compare_digest(_expected_signature(secret, timestamp, raw_body), signature)


def _event_id(payload: dict, raw_body: bytes) -> str:
    for key in ("event_id", "eventId", "eventID"):
        value = payload.get(key)
        if value:
            return str(value)[:80]
    return hashlib.sha256(raw_body).hexdigest()[:40]


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(ratelimit(key="ip", rate="60/m", method="POST", block=True), name="dispatch")
class CashfreeWebhookView(View):
    http_method_names = ["post"]

    def post(self, request):
        secret = getattr(settings, "CASHFREE_WEBHOOK_SECRET", "")
        if not secret:
            # Fail closed: an unconfigured receiver must not accept events.
            return JsonResponse({"detail": "Webhook receiver not configured."}, status=503)

        raw_body = request.body
        timestamp = request.headers.get("x-webhook-timestamp", "")
        signature = request.headers.get("x-webhook-signature", "")
        if not _signature_ok(secret=secret, timestamp=timestamp, signature=signature, raw_body=raw_body):
            logger.warning("Cashfree webhook rejected: bad signature or stale timestamp")
            return JsonResponse({"detail": "Invalid signature."}, status=401)

        try:
            payload = json.loads(raw_body.decode() or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({"detail": "Malformed payload."}, status=400)

        event_id = _event_id(payload, raw_body)
        event_type = str(payload.get("type") or payload.get("event_type") or "")[:80]
        try:
            # The savepoint keeps the inevitable duplicate-key error from
            # poisoning the caller's outer transaction.
            with transaction.atomic():
                event = WebhookEvent.objects.create(
                    provider="cashfree",
                    event_id=event_id,
                    event_type=event_type,
                    signature_valid=True,
                    payload=payload,
                )
        except IntegrityError:
            # Unique (provider, event_id): a redelivery we already accepted.
            return JsonResponse({"detail": "Duplicate event ignored."}, status=200)

        result = self._dispatch(event_type, payload)
        event.processed_at = timezone.now()
        event.processing_result = result
        event.save(update_fields=["processed_at", "processing_result"])
        return JsonResponse({"detail": result}, status=200)

    def _dispatch(self, event_type: str, payload: dict) -> str:
        data = payload.get("data") or {}
        if event_type in ESIGN_HANDLED_EVENTS:
            return EsignStatusService.apply_webhook_event(event_type, data)
        if event_type in DIGILOCKER_HANDLED_EVENTS:
            return DigiLockerService.apply_webhook_event(event_type, data)
        return "ignored"
