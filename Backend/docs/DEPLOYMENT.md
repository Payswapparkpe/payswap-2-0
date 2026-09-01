# PayswapHub — Deployment & Operations

This document covers running PayswapHub in staging/production: topology, environment, migrations, backups, and day-2 operations. Local development stays in `README.md`.

## Topology

```
                ┌────────────┐
   TLS  ──────▶ │  Ingress / │  terminates TLS, sets X-Forwarded-* (overwrites, never appends)
                │  LB / CDN  │
                └─────┬──────┘
                      ▼
              ┌───────────────┐     ┌─────────────┐
              │ web (gunicorn)│────▶│ PostgreSQL  │  primary data store
              │  N≥2 replicas │     └─────────────┘
              └──────┬────────┘
                     │           ┌─────────────┐
                     ├──────────▶│    Redis    │  cache, sessions, lockout counters, Celery broker
                     │           └─────────────┘
        ┌────────────┴───────────┐
        ▼                        ▼
 ┌─────────────┐          ┌────────────┐
 │ celery      │          │ celery-beat│  django-celery-beat DatabaseScheduler
 │ (worker)    │          └────────────┘
 └─────────────┘
```

- **web** — `gunicorn core.wsgi:application -c deploy/gunicorn.conf.py`; runs `manage.py migrate` on container start.
- **Static files** — WhiteNoise (compressed, manifest-hashed) serves from the web container; a CDN in front is recommended but not required.
- **Media (KYC documents)** — local `MEDIA_ROOT` volume by default. For multi-replica or durable deployments, move to S3-compatible object storage (see below).

## Container

```bash
docker compose up --build        # web + celery + beat + postgres + redis
docker compose exec web python manage.py bootstrap_local   # first-run seed (dev passwords — change them)
docker compose exec web python manage.py seed_payswaphub   # RBAC + notification catalog seed
```

The image runs as a non-root `app` user, collects static at build time, and health-checks `/healthz/`. Orchestrators should probe:

- **Liveness:** `GET /healthz/` → 200
- **Readiness:** `GET /readyz/` → 200 (503 when Postgres or Redis is unreachable)

## Environment

All configuration is environment-driven (see `.env.example`). Production-required values:

| Variable | Notes |
|---|---|
| `SECRET_KEY` | 50+ random chars; rotate via overlap deploys |
| `APP_ENV` | `production` — enables HSTS, secure cookies, SSL redirect, manifest static |
| `ALLOWED_HOSTS` | exact hostnames; `*` is rejected at boot in production |
| `CSRF_TRUSTED_ORIGINS` | `https://` origins only |
| `ADMIN_URL` | obscure path recommended; combine with `ADMIN_ALLOWED_IPS` |
| `ADMIN_ALLOWED_IPS` | CIDR allowlist for Django admin — optional; empty means no IP restriction (recommended in production) |
| `ADMIN_REQUIRE_OTP` | `True` in production — authenticator mandatory for platform admins (portal + Django admin); optional for all other users |
| `ADMIN_TRUST_X_FORWARDED_FOR` | `True` **only** when the ingress overwrites XFF |
| `FIELD_ENCRYPTION_KEY` | Fernet key protecting PAN/GSTIN/CIN/LLPIN at rest; loss = data loss, back it up with the DB |
| `CASHFREE_WEBHOOK_SECRET` | required for `POST /webhooks/cashfree/`; receiver fails closed when empty |
| `SENTRY_DSN` | error telemetry; PII scrubbed (`send_default_pii=False`) |

Database/Redis/email/SMS/Cashfree variables follow `.env.example`. Email sends through SES SMTP by default; set `EMAIL_BACKEND=integrations.ses.SesEmailBackend` with the `AWS_SES_*` keys for the API backend.

## Kaleyra SMS

Transactional SMS uses the Kaleyra JSON SMS API (`POST {KALEYRA_BASE_URL}/v1/{SID}/sms/json`) with DLT-approved sender `KALEYRA_SENDER` (PAYSWAP). Required env: `KALEYRA_SID`, `KALEYRA_API_KEY`, `KALEYRA_SENDER`. Optional: `KALEYRA_ENTITY_ID`, `KALEYRA_DLT_TEMPLATES` (JSON map of catalog keys to DLT template IDs), `KALEYRA_WEBHOOK_SECRET` for `POST /webhooks/kaleyra/dlr/`.

**IP whitelist:** Kaleyra API keys can restrict callers by IP. Add every environment's **egress** address (NAT / load-balancer outbound IP, not the private instance IP):

```bash
curl -s https://ifconfig.me
```

Update the Kaleyra console (API Keys → whitelist) whenever egress changes. Delivery reports are posted to `/webhooks/kaleyra/dlr/` with HMAC `X-Kaleyra-Signature` (hex SHA-256 of the raw body using `KALEYRA_WEBHOOK_SECRET`). The receiver fails closed when the secret is empty.

**DLT:** Indian transactional SMS requires a registered entity ID and per-template DLT IDs. Empty `KALEYRA_ENTITY_ID` / missing map entries omit those fields (operators will reject production traffic).

**Key rotation:** If an API key appears in chat, tickets, or a committed file, revoke it in the Kaleyra console and put the replacement only in the secret manager / `.env` (gitignored).

## Migrations & deploys

1. Deploy new image (container start runs `migrate --noinput` before gunicorn starts).
2. All migrations are backwards-compatible within a release: new columns are nullable or defaulted; destructive changes ship in a follow-up release.
3. Rollback: redeploy previous image. Do **not** roll back across a destructive migration.

## Background jobs

- Broker/result backend: Redis DB 1/2 (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`).
- Beat uses `django_celery_beat.schedulers:DatabaseScheduler` (see compose).
- Sensitive payloads (OTP codes) are Fernet-encrypted inside task arguments — broker contents are not plaintext secrets.

## Backups

| Asset | Method | Frequency | Retention |
|---|---|---|---|
| PostgreSQL | `pg_dump --format=custom` (or managed snapshots) | daily + pre-deploy | 30 days |
| `MEDIA_ROOT` (KYC docs) | object-storage versioning or `rsync` snapshot | daily | 30 days |
| `FIELD_ENCRYPTION_KEY` / `.env` | secret manager (Vault/SSM/Secrets Manager) | on change | indefinite |

Automation in this repo: `.github/workflows/backup.yml` runs daily when `BACKUP_DATABASE_URL` and `BACKUP_S3_BUCKET` repository secrets are set (`pg_dump --format=custom` uploaded as an encrypted object). The quarterly restore drill remains a human-operated checklist against a scratch database.

**Restore drill (run quarterly):** restore the latest dump into a scratch database, boot the app against it with a copy of `FIELD_ENCRYPTION_KEY`, sign in, open one merchant's documents, and confirm an encrypted onboarding step renders. A backup that has never been restored is a rumor.

## Object storage plan (media)

`FileSystemStorage` is the default. Set `AWS_STORAGE_BUCKET_NAME` to switch `STORAGES["default"]` to S3 (`django-storages`). Enable bucket versioning + block public access; documents are served through permission-checked download views, never public object URLs. Migrate existing objects with `aws s3 sync media/ s3://bucket/` before cutting over.

## Security posture checklist (production)

- [ ] `APP_ENV=production`, `DEBUG` unset/False
- [ ] `ALLOWED_HOSTS` exact, `ADMIN_REQUIRE_OTP=True` (authenticator mandatory for platform admins), `ADMIN_ALLOWED_IPS` set if an IP allowlist is wanted
- [ ] Ingress overwrites `X-Forwarded-For` before enabling `ADMIN_TRUST_X_FORWARDED_FOR`
- [ ] `CASHFREE_WEBHOOK_SECRET` set and endpoint verified with a signed test event
- [ ] Sentry DSN set; `/readyz/` wired into the LB health check
- [ ] Postgres + Redis not exposed to the public internet
- [ ] Backups scheduled and one restore drill completed
