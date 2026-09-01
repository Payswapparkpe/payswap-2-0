# Payswap UI/UX + Global Launch Checklist

Use this checklist before promoting any release to staging/production.

## UX Quality
- Consistent spacing/radius/color tokens are used (no new hardcoded one-off hex values).
- Primary CTA style is consistent across Auth, App, Admin, and Desk.
- All async actions show visible feedback (loading + success/error toast).
- Empty states exist for tables/boards/wizards where data can be absent.
- Mobile navigation is usable on widths below 960px.

## Accessibility
- Every icon-only button has an `aria-label`.
- Keyboard users can open rows/cards that are clickable by mouse.
- Focus ring is clearly visible for all interactive controls.
- Error and success messages are announced via `role="alert"` or live region.
- Color contrast is checked for muted text on light surfaces.

## Global Readiness
- Locale preset updates currency/date/phone display correctly.
- No hardcoded `INR`/`+91` is left in newly touched screens.
- Translation keys are added for new reusable labels.
- RTL-safe logical properties are used in new layout CSS.
- Market-specific validation logic is behind market config where applicable.

## Performance and Stability
- Heavy screens show loading state quickly (`<200ms` perceived response).
- Admin layout chunk is lazy loaded separately from admin list/detail chunks.
- Onboarding initial load has a loading state before data appears.
- `npm run build` passes without errors.
- Basic smoke flow passes: login -> verify -> app home -> orders -> admin -> desk.
