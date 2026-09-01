# Account Hub — Master Plan (Angular `/app/account` + Merchant API)

**Version:** 2026-09-01  
**Scope:** Payswap corporate partner console — account activation area and everything it touches  
**Goal:** Ek systematic source of truth — kya hai, kya banana hai, API kahan/kyun, Cashfree Secure ID ka unified design

---

## 1. Scope — `/app/account` se kya cover hota hai

Angular console me **Account** group ke routes (parent: `/app`, guard: `verifiedGuard`):

| Route | Component | Account hub se relation |
|-------|-----------|-------------------------|
| `/app/account` | `AccountHubComponent` | **Main hub** — KYC / KYB / Agreement status cards |
| `/app/onboarding` | `OnboardingWizardComponent` | KYC + KYB data entry (8 steps) |
| `/app/agreement` | `AgreementComponent` | Partner e-sign (Cashfree eSign) |
| `/app/business` | `BusinessProfileComponent` | Read-only business summary |
| `/app/bank` | `BankProfileComponent` | Read-only settlement account |
| `/app/documents` | `DocumentsProfileComponent` | Read-only document checklist |
| `/app/settings` | `SettingsComponent` | Session, locale, demo reset |

**Hub par dikhne wale 3 pillars (UI):**

1. **01 — KYC** — individual identity (PAN, signatory, owner, DigiLocker Aadhaar)
2. **02 — KYB** — entity, GSTIN/CIN, bank, documents, admin review
3. **03 — Agreement** — partner eSign → admin countersign → `activated`

**Summary panel:** legal name, entity type, PAN, signatory/owner relation, ordering mode (test/live).

---

## 2. Architecture principles (backend + frontend)

### 2.1 Single merchant API namespace

Saari partner JSON APIs **ek hi mount point** par:

```
/api/merchant/...
```

Router file: `Backend/api/urls.py`  
Implementation: `Backend/api/*.py` (topic-wise files, ek hi package)

| File | Responsibility |
|------|----------------|
| `api/auth.py` | Login, register, verify OTP, me, logout, password reset |
| `api/onboarding.py` | Onboarding wizard GET/PUT/submit, pincode, documents upload |
| `api/agreements_api.py` | Agreement fetch, eSign start, PDF download |
| `api/orders_api.py` | Catalog, orders (commerce — account ke baad) |
| `api/serializers.py` | Django domain → Angular JSON shape |
| `api/mixins.py` | `JsonView`, CSRF, `MerchantRequiredMixin`, errors |
| **`api/verification_api.py`** *(planned)* | **Cashfree Secure ID — saare verification products ek jagah** |
| **`api/account_api.py`** *(planned)* | Profile, preferences, sessions summary (account hub extras) |

**Kyun alag files:** Har service ka domain logic alag app me rehta hai (`verification/`, `accounts/`, `merchants/`). API layer sirf HTTP + auth + serialization — **Cashfree jaisa ek client, ek verification API module**.

### 2.2 Cashfree Secure ID — unified verification module (target design)

Pattern: **ek HTTP API surface**, andar **product-specific handlers**, sab **`integrations/cashfree.py`** + **`verification/services.py`** use karein.

```
Angular VerificationService (real HTTP)
        │
        ▼
POST /api/merchant/verification/     ← single entry (action/kind based)
GET  /api/merchant/verification/status/
GET  /api/merchant/verification/records/   (planned detail)
        │
        ▼
api/verification_api.py              ← NEW: consolidate onboarding.py verification views
        │
        ▼
verification/services.py           ← domain: cache, consent, merchant status flags
verification/providers.py          ← CashfreeVerificationProvider
integrations/cashfree.py           ← HTTP client (PAN, GSTIN, bank, IFSC, DigiLocker, eSign)
integrations/webhooks.py           ← HMAC webhooks (DigiLocker, eSign)
```

**Cashfree products — account/KYC/KYB me use:**

| Product | Cashfree API | Account use | API `kind` / `action` |
|---------|--------------|-------------|------------------------|
| PAN Lite | `POST /pan-lite` | Signatory / owner PAN | `pan` |
| GSTIN | `POST /gstin` | Business KYB | `gstin` |
| Bank sync | `POST /bank-account/sync` | Settlement account | `bank` |
| IFSC | `POST /ifsc` | Branch validation | `ifsc` |
| DigiLocker | verify-account → create-url → status | Aadhaar KYC | `aadhaar_start`, `aadhaar_status` *(planned API)* |
| eSign | document upload + `/esignature` | Agreement (alag flow) | `agreements/` POST `start_esign` |
| Name match | name-match API | Signatory vs PAN name *(optional)* | `name_match` *(planned)* |

Reference: `Backend/docs/cashfree-verification-plan.md` (official contract, webhook signature rules).

**eSign agreement alag endpoint par rahega** (`/api/merchant/agreements/`) — same Cashfree client, alag business lifecycle — lekin verification module jaisa hi systematic.

### 2.3 Frontend service map

| Angular service | Aaj kya karta hai | Target |
|-----------------|-------------------|--------|
| `OnboardingService` | GET/PUT `/merchant/onboarding/`, submit, signAgreement | Same + hub refresh |
| `VerificationService` | **Mock only** (browser delay) | **Real** → `/merchant/verification/*` |
| `AuthService` | Auth + verify OTP | Same |
| `ApiService` | CSRF + HTTP wrapper | Same |
| **`AccountService`** *(planned)* | — | Hub-specific: status snapshot, blockers, preferences |

---

## 3. Kya ho chuka hai (Implemented)

### 3.1 Backend — merchant JSON API (live)

| Status | Method | Path | File | Kyun banaya |
|--------|--------|------|------|-------------|
| Done | POST | `/api/merchant/auth/*` | `auth.py` | Partner login/register/session |
| Done | GET/PUT | `/api/merchant/onboarding/` | `onboarding.py` | Wizard state Angular shape |
| Done | POST | `/api/merchant/onboarding/submit` | `onboarding.py` | Admin review queue |
| Done | GET | `/api/merchant/onboarding/pincode/` | `onboarding.py` | India Post autofill |
| Done | POST | `/api/merchant/onboarding/documents/` | `onboarding.py` | Server-side file storage |
| Done | POST | `/api/merchant/verification/start` | `onboarding.py` | Cashfree PAN/GSTIN/bank/collected |
| Done | GET | `/api/merchant/verification/status` | `onboarding.py` | Aggregate kyc/kyb/bank flags |
| Done | GET/POST | `/api/merchant/agreements/` | `agreements_api.py` | Agreement + eSign start |
| Done | GET | `/api/merchant/agreements/<id>/download/` | `agreements_api.py` | Executed PDF |

**Cashfree domain (server-side, portal + API dono use karte hain):**

- `integrations/cashfree.py` — HTTP client
- `verification/services.py` — verify_pan, verify_gstin, verify_bank, reuse cache, consent
- `verification/digilocker.py` — Aadhaar via DigiLocker (**abhi sirf Django HTML portal**)
- `integrations/services.py` — ESignService
- Webhooks: `POST /webhooks/cashfree/`

### 3.2 Angular — account area (UI)

| Status | Part | Notes |
|--------|------|-------|
| Done | Account hub UI | 3 cards + summary; reads `OnboardingService.application` |
| Done | Onboarding wizard | 8 steps; PUT/GET real API |
| Done | Profile read-only pages | business / bank / documents |
| Done | Agreement page UI | Hardcoded MSA text; POST `start_esign` only |
| Done | Settings | Logout, locale, local demo reset |
| Done | Console layout | Loads onboarding on init; nav + status chip |

### 3.3 Auth fixes (recent session)

- CSRF trusted origins for `:4200`
- Fresh CSRF before each POST (`ApiService`)
- `/api/merchant/auth/verify` for logged-in OTP
- Demo user `merchant@payswap.local` verified via `bootstrap_local`

---

## 4. Kya abhi mock / incomplete hai (Gaps)

### 4.1 Angular gaps (account flow)

| Gap | Impact | Fix |
|-----|--------|-----|
| `VerificationService` mock | PAN/GSTIN/bank/DigiLocker wizard me fake success | Wire to `/merchant/verification/*` |
| Documents base64 in PUT body | Large JSON; server doc API unused | Use `POST onboarding/documents/` multipart |
| Agreement hardcoded clauses | Legal text server se match nahi | GET `/merchant/agreements/` body |
| eSign no `redirectUrl` handling | Cashfree signing link open nahi hota | POST response → `window.location` |
| Pincode API unused | Manual address only | Call `/onboarding/pincode/` |
| Verification status thin | Hub par server flags sync nahi | Expand status API + hub poll |
| Settings not persisted | Locale client-only | Account preferences API |
| `approveDemo()` dead code | Confusion | Remove or hide behind dev flag |

### 4.2 Backend gaps (portal-only → API chahiye)

| Feature | Portal today | API needed for Angular |
|---------|--------------|------------------------|
| DigiLocker Aadhaar start/status | `/merchant/verification/` | `verification` action `aadhaar_*` |
| Document list + download + reject reason | `/merchant/documents/` | `GET documents/`, `GET documents/<id>/download/` |
| Verification history | Staff/admin views | `GET verification/records/` |
| Verification blockers (agreement gate) | Template helper | Include in status or hub endpoint |
| Notification preferences | Profile POST | `PUT account/preferences` |
| Sessions list / revoke | `/merchant/sessions/` | `GET/DELETE account/sessions` |
| Security (TOTP, MPIN) | HTML forms | Phase 2 — optional for account hub |
| Profile contact update | ProfileService portal | `PATCH account/profile` |

---

## 5. Part-by-part plan — kya banana hai

### 5.1 `/app/account` — Account Hub

**Aaj:** Sirf `onboarding_payload` se derived flags (`kycDone`, `kybApproved`, `partnerSigned`, `isLive`).

**Banana hai:**

1. **Backend:** `GET /api/merchant/account/` *(or extend onboarding GET)* — ek response me:
   - `pillars`: kyc / kyb / agreement `{ status, label, cta, locked, blockers[] }`
   - `summary`: legal name, entity, PAN (masked), signatory relation, ordering mode
   - `verification`: Cashfree-backed flags + pending actions
2. **Angular:** Hub optional `AccountService.loadHub()` — layout init par; cards server labels use karein
3. **No mock** — sab server truth

**API kyun:** Hub ko wizard payload se alag rakhna; future me orders/notifications bhi summary me aa sakte hain bina giant onboarding JSON.

---

### 5.2 KYC — Onboarding steps + Cashfree Secure

**Steps:** signatory → profile → owner → identity → UBO → bank → documents → review

| Verification | Angular step | Cashfree product | API today | API target |
|--------------|--------------|------------------|-----------|------------|
| Signatory PAN | step-signatory | PAN Lite | mock | `POST verification/start { kind: pan }` |
| Owner PAN | step-owner | PAN Lite | mock | same |
| GSTIN / CIN | step-profile | GSTIN / registry | mock | `kind: gstin` |
| Bank + IFSC | step-bank | bank sync + IFSC | mock | `kind: bank`, `kind: ifsc` |
| Aadhaar | step-identity | DigiLocker | mock | **`kind: aadhaar_start` → redirectUrl** |
| Collected batch | step-review submit | all pending | partial | `kind: collected` on submit |

**Backend refactor (recommended):**

Move `VerificationStartView` + `VerificationStatusView` from `onboarding.py` → **`api/verification_api.py`**

```python
# Target shape — ek hi view, action dispatch (Cashfree products)
POST /api/merchant/verification/
{
  "action": "start" | "status" | "sync",
  "kind": "pan" | "gstin" | "bank" | "ifsc" | "aadhaar" | "collected" | "name_match",
  ...payload
}
```

**Angular:** Replace `core/services/verification.service.ts` mock with real `ApiService` calls; map responses to existing step UI types.

**Kyun ek API file:** Cashfree ke saare verification products ek client se — portal aur Angular dono same entry point; naya product = `kind` + service method, alag URL nahi.

---

### 5.3 KYB — Admin review + documents

| Item | Backend | Angular |
|------|---------|---------|
| Submit for review | `POST onboarding/submit` Done | step-review Done |
| Document upload | `POST onboarding/documents/` Done | **Wire multipart** from step-documents |
| Document status on hub | DocumentReviewService | Show pending/approved/rejected on `/app/documents` |
| Admin approve/reject | Django employee portal | Not Angular — hub shows `under_review` |

---

### 5.4 Agreement — `/app/agreement`

| Item | Status | Next |
|------|--------|------|
| Fetch agreement text + status | API exists GET | Angular GET use karo, hardcoded HTML hatao |
| Partner eSign | POST `start_esign` | Handle `redirectUrl` / `signingLink` → Cashfree |
| Webhook completion | Done server-side | Angular poll `GET agreements/` or onboarding refresh |
| Admin countersign | Django admin | Hub label: `pending_admin_sign` |
| Download executed PDF | API exists | Link on agreement page when `agreementDone` |

Cashfree: **eSign** (Secure ID) — verification module se alag endpoint, same `integrations/cashfree.py`.

---

### 5.5 Profile pages — business / bank / documents

**Aaj:** Read-only; edit → `/app/onboarding`.

**Phase 1:** Server data only (onboarding GET) — **Done enough**.

**Phase 2 (optional):** Lightweight `PATCH` for contact fields without full wizard.

---

### 5.6 Settings — `/app/settings`

**Phase 1:** Logout API — Done.

**Phase 2:** `GET/PUT /api/merchant/account/preferences` — notification toggles (portal parity).

---

## 6. API inventory — complete target list

### 6.1 Existing (keep, may move file)

```
GET    /api/csrf/
POST   /api/merchant/auth/register
POST   /api/merchant/auth/login
POST   /api/merchant/auth/logout
GET    /api/merchant/auth/me
POST   /api/merchant/auth/verify
POST   /api/merchant/auth/password-reset
GET    /api/merchant/onboarding/
PUT    /api/merchant/onboarding/
POST   /api/merchant/onboarding/sububmit
GET    /api/merchant/onboarding/pincode/
POST   /api/merchant/onboarding/documents/
POST   /api/merchant/verification/start      → migrate to verification/
GET    /api/merchant/verification/status     → migrate to verification/
GET    /api/merchant/agreements/
POST   /api/merchant/agreements/
GET    /api/merchant/agreements/<id>/download/
```

### 6.2 To build (account hub priority)

| Priority | Method | Path | Purpose |
|----------|--------|------|---------|
| P0 | POST | `/api/merchant/verification/` | Unified Cashfree actions (replace `/start`) |
| P0 | GET | `/api/merchant/verification/status/` | Rich status + blockers + digilocker pending |
| P0 | — | Angular `VerificationService` | Remove mock |
| P0 | — | Angular agreement | GET agreement + eSign redirect |
| P1 | POST | `/api/merchant/verification/` `kind:aadhaar` | DigiLocker URL for Angular |
| P1 | GET | `/api/merchant/account/` | Hub snapshot (pillars + summary) |
| P1 | — | step-documents | Multipart upload API |
| P2 | GET | `/api/merchant/documents/` | List + statuses |
| P2 | GET | `/api/merchant/documents/<id>/download/` | Download |
| P2 | PUT | `/api/merchant/account/preferences` | Notification prefs |
| P3 | GET/DELETE | `/api/merchant/account/sessions` | Session management |

---

## 7. Implementation phases (recommended order)

### Phase 0 — Foundation (1–2 days)

- [ ] Create `api/verification_api.py`; move views from `onboarding.py`
- [ ] Add unified `POST /api/merchant/verification/` with `action` + `kind`
- [ ] Expand `GET verification/status` (blockers, digilocker, last errors)
- [ ] Angular: real `VerificationService` (PAN, GSTIN, bank, IFSC)
- [ ] Wire pincode in profile step

### Phase 1 — Account hub truth (2–3 days)

- [ ] `GET /api/merchant/account/` hub payload
- [ ] Hub cards use server labels/blockers
- [ ] Documents: multipart upload in wizard
- [ ] Agreement: GET text + eSign redirect handling

### Phase 2 — Aadhaar DigiLocker (2–3 days)

- [ ] API: `aadhaar_start` → consent + redirect URL
- [ ] API: `aadhaar_status` / webhook-driven refresh
- [ ] Angular identity step: open Cashfree DigiLocker, return poll status
- [ ] `FEATURE_DIGILOCKER` + sandbox credentials in `.env`

### Phase 3 — Polish (ongoing)

- [ ] Document list/download API + `/app/documents` enrichment
- [ ] Account preferences API + settings
- [ ] Remove `MockApiService` from onboarding path
- [ ] Tests: `pytest` for verification API + Cashfree provider mocks

---

## 8. Environment & dependencies

| Variable | Use |
|----------|-----|
| `CASHFREE_CLIENT_ID` / `CASHFREE_CLIENT_SECRET` | Secure ID API |
| `CASHFREE_ENV` | sandbox vs production |
| `CASHFREE_WEBHOOK_SECRET` | DigiLocker + eSign webhooks |
| `FEATURE_DIGILOCKER` | Gate Aadhaar flow |
| `FEATURE_ESIGN` | Gate agreement signing |
| `VERIFICATION_CACHE_DAYS` | Reuse successful checks |
| `FIELD_ENCRYPTION_KEY` | OTP + PII encryption in notifications |
| `AUTH_TEST_MODE` / `TEST_OTP` | Local dev only (`123456`) |

---

## 9. File reference (quick navigation)

### Backend

```
Backend/api/urls.py
Backend/api/auth.py
Backend/api/onboarding.py
Backend/api/agreements_api.py
Backend/api/serializers.py
Backend/api/mixins.py
Backend/integrations/cashfree.py
Backend/integrations/services.py          # ESignService
Backend/integrations/webhooks.py
Backend/verification/services.py        # Domain VerificationService
Backend/verification/digilocker.py
Backend/verification/providers.py
Backend/merchants/services.py           # Onboarding state machine
Backend/docs/cashfree-verification-plan.md
```

### Angular (`payswap-console`)

```
src/app/app.routes.ts
src/app/features/account/account-hub.component.ts
src/app/features/account/agreement.component.ts
src/app/features/onboarding/wizard/
src/app/features/onboarding/steps/
src/app/features/profile/
src/app/core/services/onboarding.service.ts
src/app/core/services/verification.service.ts   ← mock → replace
src/app/core/services/api.service.ts
src/app/core/models/onboarding.models.ts
```

---

## 10. Success criteria (account hub “done”)

1. `/app/account` cards reflect **server** KYC/KYB/agreement state (Cashfree + admin), not client guesses.
2. Onboarding wizard me **koi verification mock nahi** — sab `POST /api/merchant/verification/`.
3. Aadhaar **DigiLocker** Angular se start + complete (Cashfree Secure ID).
4. Agreement **server-generated text** + eSign redirect + webhook-driven status on hub.
5. Documents **server-stored** via multipart API; hub/documents pages show review status.
6. Saari nayi merchant APIs **`/api/merchant/`** ke under, verification **`api/verification_api.py`** me consolidated.

---

## 11. Decision log

| Decision | Reason |
|----------|--------|
| Single `/api/merchant/` tree | One proxy, one auth model, one CSRF policy |
| `verification_api.py` alag file | Cashfree products ek jagah; onboarding.py slim |
| eSign stays `agreements_api.py` | Different lifecycle + legal PDF, same Cashfree client |
| Portal HTML routes remain | Staff/admin workflows; Angular sirf corporate partner |
| Test OTP `123456` | Dev only; production me `AUTH_TEST_MODE=False` |
| No offline Aadhaar OTP | Cashfree discontinued — DigiLocker only |

---

*Is document ko implement karte waqt update karein: checkbox tick + PR link. Ye file account hub ka single source of truth hai.*
