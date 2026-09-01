# Payswap Partner Console — How to Run & Access

Angular frontend for prepaid cards and brand vouchers.
Corporate partners use `/app`. Payswap admins use `/admin`.
Data is mocked in the browser (`localStorage`). No backend is required.

---

## Requirements

- Node.js **18+** (Node 20 or 22 recommended)
- npm (comes with Node)

Check versions:

```bash
node -v
npm -v
```

---

## Setup & run

```bash
# 1. Unzip this package, then open the project folder
cd payswap-console

# 2. Install dependencies
npm install

# 3. Start the development server
npm start
```

Open in the browser:

**http://localhost:4200**

Stop the server with `Ctrl + C`.

### Other useful commands

```bash
npm run build          # production build → dist/payswap-console/browser
npm run preview        # serve that build at http://localhost:4173
npx ng serve --port 4300   # run on a different port if 4200 is busy
```

---

## Host this build (static site)

The share zip includes a ready `hosting/` folder. Upload **only that folder’s files** (not `payswap-console/` — Cloudflare’s uploader rejects TypeScript source).

Cloudflare CLI:

```bash
cd payswap-console
npm install
npx wrangler login
npm run deploy
```

SPA fallback files (`_redirects`, `.htaccess`, `web.config`) are included so `/app` and `/admin` routes work.

Full steps: **HOSTING.md** (and HOSTING.txt).

---

## Login / demo accounts

Password for all accounts: **`Payswap@123`**  
OTP (SMS, email, Aadhaar, reset): **`123456`**

| Role | Email | Where you land |
| --- | --- | --- |
| Corporate (KYC pending) | `priya@acme.in` | http://localhost:4200/app |
| Corporate (KYC submitted) | `rohit@giftmart.in` | http://localhost:4200/app |
| Payswap admin | `admin@payswap.in` | http://localhost:4200/admin |

Or register a new corporate partner at http://localhost:4200/register.

---

## What each area does

### Partner console (`/app`)

- **Home / Orders** — order overview
- **Brand vouchers** — brand catalog (select a brand, then denomination and quantity)
- **Prepaid cards** — meal / reward card loads
- **KYC · KYB · Agreement** — activation only
- **Business / Bank / Settings** — profile and session

### Admin panel (`/admin`)

- **Overview** — pending KYC, agreements, orders
- **Partners** — approve / send back KYC·KYB, countersign agreement
- **Orders** — mark orders fulfilled

---

## Activation flow (important)

1. Partner verifies **KYC** (person), then entity **KYB**, and submits  
2. Admin opens **Partners** → **Approve KYC / KYB**  
3. Partner opens **Agreement** → **eSign**  
4. Admin → **Countersign agreement** → partner becomes **Live**

Until live, the workspace stays in **Test** mode (catalog / demo orders still work).

---

## Demo tips

- DigiLocker account is missing if signatory PAN ends with **`9`**
- PAN / GSTIN / CIN verification fails if the number ends with **`0`**
- Penny-drop “mismatch” if bank account number ends with **`0`**
- Settings → **Reset local demo data** clears this browser’s mock DB
- Storage key: `payswap-console-db-v4` (Chrome DevTools → Application → Local Storage)

---

## Project structure (short)

```
payswap-console/
  src/app/
    features/auth/        Login, register, OTP
    features/console/     Partner shell + home
    features/commerce/    Gifting, vouchers, cards, orders
    features/onboarding/  KYC / KYB wizard
    features/account/     Activation hub + agreement
    features/admin/       Admin panel
    core/                 Models, mock API, guards
  README.md               Product summary
  HOW_TO_RUN.md           Local run + demo logins
  HOSTING.md              Upload / Netlify / Vercel / cPanel / nginx
```

---

## Sharing notes for developers

- Source in this zip **excludes** `node_modules`. Run `npm install` after unzip if you need to change code.
- A pre-built static site is in the zip’s **`hosting/`** folder — upload that to go live without building.
- Frontend-only mock; no live SMS, DigiLocker, registry, or bank APIs.
- Stack: Angular 19, Angular Material, SCSS, standalone components.

If something fails after unzip, delete `node_modules` and `package-lock.json`, then run `npm install` again.
