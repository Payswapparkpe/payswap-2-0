# Payswap Partner Console

Angular frontend for **prepaid cards** and **brand vouchers**.

- **Corporate partners** — order brand vouchers and meal / reward prepaid cards
- **Admin** — verify KYC / KYB and countersign partner agreements

All APIs are mocked in `localStorage` (key `payswap-console-db-v4`).

## Run

```bash
cd payswap-console
npm install
npm start
```

Open http://localhost:4200

## Host

Production files are the `hosting/` folder in the share zip (see `HOSTING.md`). From source:

```bash
npm run build
npm run preview
```

Publish `dist/payswap-console/browser`.

## Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Corporate (KYC pending) | `priya@acme.in` | `Payswap@123` |
| Corporate (submitted) | `rohit@giftmart.in` | `Payswap@123` |
| Admin | `admin@payswap.in` | `Payswap@123` |

OTP everywhere: `123456`

## Activation flow

1. Partner verifies KYC (person), then entity KYB, and submits
2. Admin **Approves KYC / KYB** (`/admin/partners`)
3. Partner **eSigns** agreement (`/app/agreement`)
4. Admin **Countersigns** → partner goes live

## Product areas

Partner: Home, Orders, Brand vouchers, Prepaid cards, Account activation  
Admin: Overview, Partners, Orders
