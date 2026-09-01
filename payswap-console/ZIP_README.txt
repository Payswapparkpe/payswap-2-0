Payswap Partner Console
=======================

This zip is ready to host. Demo data stays in the browser. No backend required.

1) Go live
   Cloudflare dashboard: upload ONLY the "hosting" folder (not payswap-console).
   Cloudflare CLI: cd payswap-console && npm install && npx wrangler login && npm run deploy
   Other hosts: upload every file inside "hosting/".

   Details: HOSTING.txt / HOSTING.md

2) Run on a laptop (developers)
   cd payswap-console
   npm install
   npm start
   Open http://localhost:4200

   Details: HOW_TO_RUN.txt / HOW_TO_RUN.md

Demo logins (password Payswap@123, OTP 123456)
  Corporate  priya@acme.in
  Submitted  rohit@giftmart.in
  Admin      admin@payswap.in

Host at the domain root, e.g. https://console.yourdomain.com
