# Entity KYC/KYB Design — Individual, Partnership, NGO

**Date:** 2026-09-01  
**Status:** Approved (partner list: **Option C**)

## Summary

Extend onboarding so individuals verify Udyam + DigiLocker + bank; partnership/NGO collect all partner/trustee KYC via DigiLocker **or** self-attested upload with OCR; signatory/director branching controls whether only BR is needed or auth-signatory Aadhaar/PAN is also required.

## Partner / trustee registry (Option C)

- **Manual add:** User enters name, PAN, designation for each partner/trustee.
- **Optional deed upload:** Partnership deed or trust deed PDF/image → OCR extracts names (when API available) and pre-fills the list; user can edit before confirming.
- Both paths merge into `registryMembers[]`; each member needs KYC (eKYC or self-attested).

## Flows by entity

### Individual
1. Person KYC (DigiLocker: Aadhaar + PAN)
2. Profile (brand/trade name)
3. Udyam Aadhar verification
4. Bank (penny drop)
5. Review

### Company / LLP (CIN)
1. Person KYC + relation (director vs auth signatory only)
2. Profile
3. Auth signatory KYC *(if opener ≠ auth signatory)*
4. Owner KYC *(if signatory ≠ owner)*
5. KYB (PAN/CIN/GST) + MCA directors
6. UBO / remaining directors KYC
7. Bank → Review

**Signatory rules:**
| Opener role | Person KYC | Documents |
|-------------|------------|-----------|
| Director (linked to MCA) | Step 1 → auto-maps | BR / BOR only |
| Auth signatory only | Step 1 Aadhaar+PAN | BR + auth instrument |
| Opener ≠ auth signatory | Opener KYC + **auth signatory KYC step** | BR |

### Partnership / NGO (no CIN)
1. Person KYC
2. Profile
3. Auth signatory KYC *(if needed)*
4. KYB: business PAN, **manual partners + optional deed OCR**, registered address (manual)
5. All partners/trustees KYC (DigiLocker or self-attested + OCR stored)
6. Auth letter / trustee resolution upload
7. Bank → Review

## KYC paths per person

| Path | UI | Backend record |
|------|-----|----------------|
| **DigiLocker** | Popup eKYC | `digilocker` snapshot on person |
| **Self-attested** | Upload signed Aadhaar/PAN form | `Document` file + `ocr_payload` JSON |

## Implementation phases

| Phase | Deliverable |
|-------|-------------|
| **P0** (this sprint) | Bug fixes, auth slots, address fix, auth-signatory step, partner registry UI, model foundation |
| **P1** | Udyam Cashfree API |
| **P2** | Smart OCR on deed + self-attested docs |
| **P3** | Backend persistence round-trip for new fields |
