# PayswapHub

PayswapHub is a merchant operations platform focused on **onboarding**, **KYC/KYB**, **commercial agreements**, and **purchase-order creation and approval**.

The platform is designed with a strong focus on **security, scalability, maintainability, reliability, and operational efficiency**.

## Current status

Status language: Implemented / Tested / Partially tested / Not started / Requires review.

### Implemented and Tested

- Three portals at `/administration/`, `/employee/`, `/merchant/` with isolated access
- Custom user model, portal login, merchant registration, login rate limit, session rotation
- Account lockout (5 failures / 10 min → 15-min lock, cache-backed) and signed-token password reset with session revocation
- Email and mobile verification codes (hashed, single-use; codes Fernet-encrypted inside Celery payloads)
- TOTP MFA enrolment and login challenge
- Session tracking and revoke
- RBAC + resource/state Policy (portal, merchant view, KYC, orders)
- Merchant onboarding state machine, entity-specific business fields, save draft, accuracy confirmation, clarification
- PII encryption at rest for onboarding PAN/GSTIN/CIN/LLPIN and beneficial-owner PAN, masked display everywhere except the executed agreement
- India Post PIN-code lookup (cached) with onboarding autofill
- Document upload and review (approve/reject with reason)
- Advanced KYC via Cashfree Verification (PAN, GSTIN, bank, DigiLocker Aadhaar) with reuse/caching and consent records
- Encrypted bank account numbers
- Agreement generate, merchant sign, Cashfree eSign, Payswap countersign, executed commercial activation
- Catalog brands/products with server-side pricing for purchase orders
- Purchase orders: create, submit, staff review/approve/reject/request-changes, amend, cancel; lifecycle ends at **APPROVED**
- A4 purchase-order PDF download with audit
- Cashfree webhook receiver for eSign and DigiLocker only (HMAC-SHA256, replay window, durable event log)
- Audit with secret redaction, request/IP/user-agent capture
- Notifications with per-user channel preferences (security alerts always deliver) and permission-scoped search
- Roles page with grant/revoke controls
- Admin KPI cards from live queries (empty states when zero)
- Server-side pagination on list views
- Health endpoints: `/healthz/` (liveness), `/readyz/` (database + cache readiness)

### Out of scope (removed)

- Payment verification and payment webhooks
- Voucher fulfilment / delivery
- Rewards / points redemption
- Support tickets, reports dashboards, and in-portal messaging inbox

### Partially tested / Requires review

- Passkeys (credential register/verify implemented; browser WebAuthn ceremony Requires review)
- Document files stored on local disk in development (production object storage plan in `docs/DEPLOYMENT.md`)

Do not treat older marketing lists below as live features. The lists in this file describe intent; **this Current status section is the source of truth.**

## Modules

### Authentication

Complete authentication and account-security management.

- Login
- Logout
- User registration
- Password management
- Email verification
- Mobile verification
- Multi-factor authentication
- Session management
- Account security

### Authorization

Centralized role and permission management.

- Roles
- Permissions
- Role-based access control
- Permission-based access control
- Department-based access
- User access management
- Administrative authorization
- Resource-level authorization

### Merchant Onboarding

Digital merchant registration, verification, approval, and activation workflow.

- Merchant registration
- Business information
- Contact verification
- KYC/KYB
- Document management
- Verification workflow
- Approval workflow
- Merchant activation
- Merchant profile management

### Agreements

Commercial agreement generation and electronic execution.

- Template generation
- Merchant review and sign
- Cashfree eSign
- Countersign and execute
- Agreement download

### Purchase orders

Catalog-backed PO create and staff approval.

- Brand/product catalog and pricing
- Merchant create / edit / submit / cancel
- Staff review / approve / reject / request changes / amend
- A4 purchase-order document

### Back Office Management

Centralized administrative and operational management.

- Dashboard
- User management
- Merchant management
- Role management
- Permission management
- Order review queues
- Audit logs

## Local development

See `docs/DEPLOYMENT.md` for environment variables and deployment notes.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_payswaphub
python manage.py runserver
```
