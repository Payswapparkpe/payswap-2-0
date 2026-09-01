# Cashfree verification / eSign build plan (17 Aug 2026)

Working companion to `docs/deep-scan-2026-08-17.md`. Contracts verified against the
official Cashfree docs (Secure ID / Verification Suite, `x-api-version: 2024-12-01`)
on 17 Aug 2026.

## Verified Cashfree contract surface

| Product | Method & path | Request keys | Result keys |
|---|---|---|---|
| PAN Lite | POST `/pan-lite` | `verification_id`, `pan`, `name`, `dob` | `reference_id`, `pan`, `name`, `dob`, `name_match`, `pan_status` |
| GSTIN | POST `/gstin` | `gstin` (lowercase) | `reference_id`, `legal_name_of_business`, `trade_name_of_business`, `gst_in_status`, address, constitution |
| Bank sync v2 | POST `/bank-account/sync` | `bank_account`, `ifsc`, optional `name`, `phone` | `reference_id`, `name_at_bank`, account status |
| Bank async v2 | POST `/bank-account/async` | + `verification_id` | result via webhook / status poll |
| IFSC v2 | POST `/ifsc` | `verification_id`, `ifsc` | `bank`, `branch`, `address`, `city`, `state`, payment-mode flags; 409 on duplicate `verification_id` |
| eSign upload | POST `/esignature/document` | multipart PDF ≤10MB | `document_id` |
| eSign create | POST `/esignature` | `verification_id`, `document_id`, `notification_modes`, `auth_type=AADHAAR`, `expiry_in_days` (≤15), `signers[]` (+`sign_positions`) | `signing_link`, `reference_id`, `verification_id` |
| eSign status | GET `/esignature?reference_id=` or `?verification_id=` | — | status + signed document URL |
| eSign webhooks | `E_SIGN_VERIFICATION_SUCCESS/FAILURE/EXPIRED` | headers `x-webhook-signature`, `x-webhook-timestamp` | signed doc URL in payload |
| DigiLocker | verify-account → create-url → get-status → get-document | consent URL (10-min validity) | statuses `PENDING/AUTHENTICATED/EXPIRED/CONSENT_DENIED`; webhooks per stage |
| Name Match | POST name-match API | two names | score 0–1 + category (Direct 1.00 / Good Partial 0.85–0.99 / Moderate 0.60–0.84 / Poor 0.34–0.59 / No Match ≤0.33) |

**Webhook signature (Secure ID, confirmed):**
`base64(HMAC-SHA256(client_secret, x-webhook-timestamp + raw_body))` — concatenation
**without** a separator, over the exact raw body. Our payments receiver used
`timestamp + "." + body`; the Secure ID receiver must use the documented no-dot form.

## Corrections to the pre-existing client (verified against docs)

1. `verify_gstin` sent `{"GSTIN": ...}` — request schema key is lowercase `gstin`.
2. eSign used `POST /esign/documents` + base64 JSON — the real contract is
   multipart `POST /esignature/document` and `POST /esignature` with
   `verification_id`/`auth_type`/`notification_modes`/`sign_positions`.
3. Aadhaar "offline OTP" (`/offline-aadhaar/otp|verify`) is **discontinued** by
   Cashfree. Current supported Aadhaar paths are **DigiLocker** (consent link +
   webhooks) and Smart OCR. We implement DigiLocker and remove the dead methods.
4. No caller-supplied `verification_id` was used anywhere — V2 APIs accept it as
   an idempotency/correlation key (409 on duplicate) and we now always send one.

## Design decisions (§76 "prefer existing infrastructure")

- Extend the existing **`verification`** app; no parallel `cashfree` app.
  HTTP stays in `integrations/cashfree.py` (hardened), domain in
  `verification/` services, provider abstraction in `verification/providers.py`.
- `VerificationRecord` becomes the canonical verification store
  (encrypted value + HMAC lookup hash + masked display, normalized statuses,
  30-day reuse via `VERIFICATION_CACHE_DAYS`). Legacy `IdentityCheck` rows stay
  readable; approval evidence gates accept either source.
- Aadhaar = DigiLocker flow, feature-gated (`FEATURE_DIGILOCKER`, default on in
  sandbox config). Face match / liveness / UPI / reverse penny drop are separate
  Cashfree products requiring account enablement — feature-gated stubs, no
  invented endpoints.
- eSign statuses never trust the browser redirect: only webhook (verified
  signature) or the Get Status API may mark an agreement signed.
- Agreements keep the existing model; add `AgreementEvent` timeline, signed-file
  storage, expiry, and a status-fetch service.
- DRF `/api/v1/` arrives in V7 scoped to verification + agreement operations,
  session-authenticated, sharing the same services and Policy checks.
