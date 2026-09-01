# Host Payswap Partner Console

This is a **static Angular app**. There is no backend. Demo data lives in the browser (`localStorage`).

Upload the **contents** of the `hosting/` folder (not the folder name itself) to the site root.

Deep links such as `/app`, `/admin`, and `/login` need an SPA fallback to `index.html`. Files for that are already in `hosting/`:

- `_redirects` — Netlify, Cloudflare Pages
- `vercel.json` — Vercel (static upload)
- `.htaccess` — Apache / cPanel
- `web.config` — IIS
- `staticwebapp.config.json` — Azure Static Web Apps
- `404.html` — GitHub Pages / Cloudflare (copy of `index.html`)

---

## Option A — drag-and-drop host (fastest)

1. Unzip `Payswap-Partner-Console.zip`
2. Open the `hosting` folder
3. Upload **all files inside it** to:

| Host | Where |
| --- | --- |
| **Netlify** | Site → Deploys → drag the `hosting` folder |
| **Cloudflare** | Dashboard upload: select **only** the `hosting` folder (not `payswap-console`). CLI: `npm run deploy` in `payswap-console/` |
| **Vercel** | `vercel hosting --yes` from the unzipped folder, or import the `payswap-console` source |
| **cPanel** | File Manager → `public_html` → upload/extract the files from `hosting/` |
| **S3 + CloudFront** | Sync `hosting/` to the bucket; set error document to `index.html` |

Open the live URL. Login: `priya@acme.in` / `Payswap@123` (OTP `123456`).

---

## Option B — build from source on the host

From `payswap-console/`:

```bash
npm install
npm run build
```

Publish folder: `dist/payswap-console/browser`

- Netlify: `netlify.toml` is already in the project
- Vercel: `vercel.json` is already in the project

---

## Cloudflare (`wrangler deploy`)

The dashboard uploader rejects the **source** folder because it contains TypeScript. Use Wrangler, or upload **only** `hosting/` (built files, no `.ts`).

From `payswap-console/`:

```bash
npm install
npx wrangler login
npm run deploy
```

That builds Angular, then deploys `dist/payswap-console/browser` as a Workers static site with SPA routing (`/app`, `/admin`, `/login`).

Config is `wrangler.jsonc`. After login, Cloudflare prints the live `*.workers.dev` URL.

Dashboard alternative: Workers & Pages → Create → Upload assets → choose the **`hosting`** folder from the zip (not the whole zip, not `payswap-console/`).

---

```bash
cd payswap-console
npm install
npm run build
npm run preview
```

Open **http://localhost:4173**

Or, after unzipping:

```bash
npx --yes serve hosting -s -l 4173
```

---

## nginx (VPS)

```nginx
server {
  listen 80;
  server_name example.com;
  root /var/www/payswap/hosting;
  index index.html;

  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

---

## Notes

- Host at the **domain root** (`https://console.example.com/`). Subfolder hosting needs a different `base href`.
- This demo does **not** call live DigiLocker or bank APIs.
- After a host cache, do a hard refresh if an old bundle is stuck.
