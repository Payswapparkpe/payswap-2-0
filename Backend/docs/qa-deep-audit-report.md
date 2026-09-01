# PayswapHub deep QA audit

**Date:** 17 August 2026  
**Environment:** local Django `runserver` on `http://127.0.0.1:8000`, PostgreSQL database `payswap_hub_qa` (the existing `payswap_hub` database still has the pre-custom-user migration history and was left untouched).  
**Method:** Playwright CLI + Cursor browser screenshots, live CSRF form posts with realistic Indian KYC data, Postgres/`AuditEvent` inspection, Django security review.

## Executive summary

The three portals isolate roles correctly, CSRF and CSP headers are present, login rate limits work, and KYC approval of a real Private Limited application succeeded end-to-end. The audit also found several high-impact defects: session revoke did not kill Django sessions, HTML files were stored as KYC documents, onboarding inputs rendered a Python dict into every field, DataTables crashed on every page without jQuery, local bootstrap users had no roles, and verification GETs issued a new code on every visit.

All in-scope findings below were fixed in this pass and covered by tests (`132 passed`). Product gaps already marked Not started in the README (backups, object storage, live Recharge) were not built.

## Environment notes

- `python manage.py check --deploy` on `DEBUG=True` development: W004 HSTS, W008 SSL redirect, W012/W016 secure cookies, W018 DEBUG. Expected for local HTTP; production settings already enable these when `APP_ENV` is staging/production.
- `bootstrap_local` created users but originally did not grant roles (F-006). Roles were granted for the live pass, then the command was fixed.
- Admin login correctly lands on `/mfa/setup/` and displays a TOTP secret (intended).

## Journeys run

| Journey | Result | Evidence |
|---------|--------|----------|
| Anonymous login, 404, legal, cookie banner | Pass | Screenshots `output/playwright/01-login-full.png`, `02-404.png`, `03-privacy.png`; GET `/logout/` = 405 |
| Bad password | Pass | HTTP 400, `LoginEvent` failure, `auth.login` audit failure |
| Open redirect `?next=https://evil.example/` | Pass | Redirected to `/merchant/` |
| Seeded merchant dashboard, onboarding, orders, documents, sessions | Pass | Screenshots 05–12; `/administration/` = 403 + `portal.denied` audit |
| New merchant register (Priya Sharma, 9876543210, PAN/CIN/GSTIN) | Pass | User `priya.sharma.qa@example.com`, merchant `PSM-000001` |
| Onboarding save/submit | Pass after field-binding bug noted | Application APPROVED; business JSON stored correctly in DB |
| KYC queue approve | Pass | `merchant.approve` audit for `PSM-000001` |
| Finance / ops login | Pass | `/employee/` 200; `/administration/` 403 |
| Admin MFA setup | Pass (gate works) | `/mfa/setup/` 200 with secret |
| Merchant order IDOR `ORD-000001` | Pass | 404 |
| HTML KYC upload | Fail then fixed | `DOC-000001` stored `malware.html` before the fix |

## Findings

### High

**F-001 — Session revoke did not invalidate Django sessions**  
Rule: session security / force logout.  
Location: [`accounts/services.py`](accounts/services.py) `SessionService.revoke`; [`portals/views/common.py`](portals/views/common.py) `SecurityActionView`.  
Impact: “Force logout” and self-service revoke left the cookie working.  
Status: **Fixed** — delete `django.contrib.sessions` rows, `revoke_all` for admin force-logout, `RevokedSessionMiddleware` rejects revoked `session_key`.

**F-002 — KYC upload accepted arbitrary files**  
Rule: untrusted uploads.  
Location: [`verification/services.py`](verification/services.py) `register_upload`.  
Evidence: live POST of `malware.html` created `documents/2026/08/malware.html`.  
Impact: stored XSS / malware in media.  
Status: **Fixed** — PDF/JPEG/PNG extension + magic bytes + content-type; HTML now rejected.

**F-003 — Weak Fernet key padding**  
Rule: encryption key handling.  
Location: [`core/crypto.py`](core/crypto.py).  
Impact: a passphrase was zero-padded into a deterministic key.  
Status: **Fixed** — require a real 44-character Fernet key; log decrypt failures.

**F-004 — Verification GET issued a new code every visit**  
Rule: OTP abuse / email flooding.  
Location: [`portals/views/common.py`](portals/views/common.py) `VerifyContactView.get`.  
Evidence: `/merchant/verify/email/` and `/verify/mobile/` showed a fresh “Development code” on GET.  
Status: **Fixed** — GET is display-only; “Send a new code” POST is rate-limited (5/m). MFA challenge POST is rate-limited (8/m).

**F-005 — Payment search skipped authorization**  
Rule: least privilege.  
Location: [`portals/search.py`](portals/search.py).  
Impact: any staff searcher could learn payment public IDs / provider references.  
Status: **Fixed** — require `payment.verify` and `merchant.view` on the related merchant.

**F-006 — `bootstrap_local` created users without roles**  
Rule: authorization seeding.  
Location: [`access/management/commands/bootstrap_local.py`](access/management/commands/bootstrap_local.py).  
Impact: seeded portal users could not pass Policy until roles were granted by hand.  
Status: **Fixed** — `Policy.grant_role` on every bootstrap user.

**F-007 — DataTables loaded without jQuery on every page**  
Rule: UI correctness / CSP-safe scripts.  
Location: [`templates/layouts/base.html`](templates/layouts/base.html).  
Evidence: Playwright console, 7× `ReferenceError: jQuery is not defined` on `/login/`.  
Status: **Fixed** — vendor scripts only on portal shells; jQuery vendored; login no longer loads DataTables.

### Medium

**F-008 — Onboarding inputs bound the whole JSON dict**  
Location: [`templates/portals/merchant/onboarding.html`](templates/portals/merchant/onboarding.html) `value="{{ step.data|default_if_none:'' }}"`.  
Evidence: after saving real CIN/PAN/GSTIN, each input showed `{'cin': 'U74999MH2018PTC123456', ...}`.  
Status: **Fixed** — per-field values and human labels from the view.

**F-009 — Non-business onboarding steps were Notes-only**  
Location: same template; bank IFSC was accepted only if posted, not shown.  
Status: **Fixed** — owners/KYC/KYB/bank field sets in [`merchants/states.py`](merchants/states.py).

**F-010 — Bank account numbers stored in step JSON**  
Location: [`merchants/services.py`](merchants/services.py) `save_step`.  
Evidence: `account_number: 50100012345678` in `OnboardingStep.data`.  
Status: **Fixed** — persist last4 only (`****5678`).

**F-011 — `reset_mfa` left TOTP devices in place**  
Location: [`portals/views/common.py`](portals/views/common.py).  
Status: **Fixed** — delete `TOTPDevice` rows.

**F-012 — Login/audit IP ignored `X-Forwarded-For` helper**  
Location: [`portals/views/auth.py`](portals/views/auth.py), [`audit/services.py`](audit/services.py).  
Status: **Fixed** — use `core.ip.client_ip`.

**F-013 — Security actions had no usable UI**  
Location: [`templates/portals/administration/security.html`](templates/portals/administration/security.html), employees table.  
Status: **Fixed** — force logout / reset MFA / suspend forms on Security and Employees.

**F-014 — Employee KYC document download was `merchant.view` only**  
Location: document download views.  
Impact: support-only staff could download KYC files.  
Status: **Fixed** — `Policy.can_download_document` requires review/KYC/finance permission for employees.

**F-015 — MFA setup re-enrolled on every GET**  
Location: `MfaSetupView.get`.  
Status: **Fixed** — reuse an unconfirmed authenticator device.

### Low

**F-016 — `.env.example` still said ParkPe**  
Status: **Fixed**.

**F-017 — Audit redaction missed PAN/GSTIN/IFSC/CIN**  
Location: [`audit/services.py`](audit/services.py) `REDACT_KEYS`.  
Status: **Fixed**.

**F-018 — `auth.register` / `onboarding.submit` audits omitted `request` (no IP)**  
Status: **Fixed** for those actions.

**F-019 — Login form sits below a tall hero on short viewports**  
Status: **Won’t restyle in this pass** — content is reachable; not a functional defect.

**F-020 — Admin Unfold CSP allows `unsafe-inline` / `unsafe-eval`**  
Location: [`core/middleware.py`](core/middleware.py) `ADMIN_CSP`.  
Status: **Accepted** — required for Unfold; portal CSP remains strict.

## Product gaps (not fixed this pass)

- Automated backups  
- Production object storage for KYC  
- Live Recharge  
- Browser WebAuthn ceremony still Requires review  
- Existing local DB `payswap_hub` cannot migrate onto `accounts.User` (inconsistent history). Use a fresh database such as `payswap_hub_qa`.

## Re-verification

- `pytest` — **132 passed**  
- New coverage in [`tests/test_qa_audit_fixes.py`](tests/test_qa_audit_fixes.py)  
- Live HTML upload, onboarding field round-trip, verify GET, and session revoke re-checked after the fixes
