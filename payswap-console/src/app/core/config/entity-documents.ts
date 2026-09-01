import { EntityType } from '../models/onboarding.models';

export interface DocumentSlot {
  id: string;
  label: string;
  hint: string;
  required: boolean;
  accept: string;
}

export const ENTITY_DOCUMENTS: Record<EntityType, DocumentSlot[]> = {
  individual: [
    { id: 'signatory_pan', label: 'PAN of signing authority', hint: 'Clear colour scan of PAN.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'address_proof', label: 'Address proof', hint: 'Aadhaar (masked), passport, voter ID, or DL.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'bank_proof', label: 'Bank account proof', hint: 'Cancelled cheque, statement, or bank letter.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  ],
  proprietorship: [
    { id: 'signatory_pan', label: 'Proprietor PAN', hint: 'Personal PAN used for the business.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'business_proof_1', label: 'Business proof 1', hint: 'GST, Udyam, Shop Act, ITR, IEC, or utility bill.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'business_proof_2', label: 'Business proof 2', hint: 'A second government proof of the firm.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'bank_proof', label: 'Bank account proof', hint: 'Name must match proprietor PAN.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  ],
  partnership: [
    { id: 'firm_pan', label: 'Partnership PAN', hint: 'PAN of the firm.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'partnership_deed', label: 'Partnership deed', hint: 'Complete stamped deed with profit-sharing ratios.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'govt_certificate', label: 'Government certificate', hint: 'Registrar of Firms or equivalent.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'auth_letter', label: 'Letter of authority', hint: 'On letterhead, appointing the authorised signatory. Required even if that person is also a partner.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'signatory_pan', label: 'Signatory PAN', hint: 'Authorised partner PAN.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'bank_proof', label: 'Cancelled cheque / statement', hint: 'Account in the firm’s name.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  ],
  llp: [
    { id: 'llp_pan', label: 'LLP PAN', hint: 'PAN of the LLP.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'coi', label: 'Certificate of Incorporation', hint: 'MCA certificate with LLPIN.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'llp_deed', label: 'LLP agreement', hint: 'Notarised deed with profit-sharing.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'board_resolution', label: 'Board resolution', hint: 'Certified board resolution appointing the authorised signatory for this Payswap account. Required for every LLP, including when the signatory is a designated partner.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'signatory_pan', label: 'Designated partner PAN', hint: 'KYC of the operating partner.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'bank_proof', label: 'Current account proof', hint: 'Cancelled cheque in LLP name.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  ],
  private_limited: [
    { id: 'company_pan', label: 'Company PAN', hint: 'Business PAN card.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'coi', label: 'Certificate of Incorporation', hint: 'CIN must be visible.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'moa', label: 'Memorandum of Association', hint: 'Certified copy of MOA.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'aoa', label: 'Articles of Association', hint: 'Certified copy of AOA.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'board_resolution', label: 'Board resolution', hint: 'Certified board resolution appointing the authorised signatory. Required for every private limited company, including when the signatory is a director or shareholder.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'gst_certificate', label: 'GST certificate', hint: 'Required if GSTIN was provided.', required: false, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'bank_proof', label: 'Cancelled cheque', hint: 'Current account in company name.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  ],
  public_limited: [
    { id: 'company_pan', label: 'Company PAN', hint: 'Business PAN card.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'coi', label: 'Certificate of Incorporation', hint: 'CIN must be visible.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'moa', label: 'Memorandum of Association', hint: 'Certified copy of MOA.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'aoa', label: 'Articles of Association', hint: 'Certified copy of AOA.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'board_resolution', label: 'Board resolution', hint: 'Certified board resolution appointing the authorised signatory. Required for every public company, including when the signatory is a director.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'listed_declaration', label: 'Listed company declaration', hint: 'If listed, UBO identification may be skipped.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'bank_proof', label: 'Cancelled cheque', hint: 'Current account in company name.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  ],
  opc: [
    { id: 'company_pan', label: 'Company PAN', hint: 'OPC PAN card.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'coi', label: 'Certificate of Incorporation', hint: 'CIN must be visible.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'moa', label: 'Memorandum of Association', hint: 'Certified copy of MOA.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'aoa', label: 'Articles of Association', hint: 'Certified copy of AOA.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'board_resolution', label: 'Board resolution', hint: 'Certified board resolution appointing the authorised signatory. Required for an OPC even when the member is the sole director.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'bank_proof', label: 'Cancelled cheque', hint: 'Current account in company name.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  ],
  trust_society_ngo: [
    { id: 'entity_pan', label: 'Entity PAN', hint: 'Trust, society, or NGO PAN. Form 60 if none.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'registration', label: 'Trust deed / registration certificate', hint: 'Deed plus registration if registered.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'tax_exemption', label: '80G / 12A certificate', hint: 'Required if tax exemption is claimed.', required: false, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'trustee_resolution', label: 'Board / trustee resolution', hint: 'Resolution appointing the authorised signatory to operate this account, even if that person is a trustee.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'bank_proof', label: 'Bank proof', hint: 'Account in the entity name.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  ],
  huf: [
    { id: 'huf_pan', label: 'HUF PAN', hint: 'PAN in the name of the HUF.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'huf_deed', label: 'HUF deed', hint: 'Deed identifying the Karta.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'karta_kyc', label: 'Karta KYC', hint: 'PAN and address proof of the Karta.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
    { id: 'bank_proof', label: 'Bank proof', hint: 'Account in HUF name.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  ],
};

export interface LobDocument {
  categories: string[];
  slot: DocumentSlot;
}

export const LOB_DOCUMENTS: LobDocument[] = [
  {
    categories: ['food'],
    slot: { id: 'fssai', label: 'FSSAI licence', hint: 'Required for food, health, and supplements.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  },
  {
    categories: ['travel'],
    slot: { id: 'iata', label: 'IATA / IRCTC certificate', hint: 'Required for tours and travel agencies.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  },
  {
    categories: ['education'],
    slot: { id: 'edu_cert', label: 'UGC / CBSE / ICSE / AICTE certificate', hint: 'Required for schools and vocational institutes.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  },
  {
    categories: ['finance'],
    slot: { id: 'sebi', label: 'SEBI / NBFC / FEMA licence', hint: 'Required for regulated financial services.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  },
  {
    categories: ['healthcare'],
    slot: { id: 'drug_licence', label: 'Drug licence', hint: 'Required for pharmacy and healthcare retail.', required: true, accept: '.pdf,.jpg,.jpeg,.png' },
  },
];

const PERSONA_SLOTS = new Set(['signatory_pan', 'signatory_id', 'signatory_kyc', 'karta_kyc', 'owner_pan', 'owner_id']);
const BANK_SLOTS = new Set(['bank_proof']);

export function kybPhysicalDocuments(
  entityType: EntityType | '',
  category: string,
  gstinProvided = false,
): DocumentSlot[] {
  return documentsFor(entityType, category, true)
    .filter((slot) => !BANK_SLOTS.has(slot.id))
    .map((slot) => (slot.id === 'gst_certificate' && gstinProvided ? { ...slot, required: true } : slot));
}

/** Bank proof (and any slots not already collected on KYC / KYB). */
export function leftoverPhysicalDocuments(
  entityType: EntityType | '',
  category: string,
  kybCollected: boolean,
  gstinProvided = false,
): DocumentSlot[] {
  const remaining = documentsFor(entityType, category, true);
  if (!kybCollected) {
    return remaining;
  }
  const kybIds = new Set(kybPhysicalDocuments(entityType, category, gstinProvided).map((slot) => slot.id));
  return remaining.filter((slot) => !kybIds.has(slot.id));
}

export function documentsFor(
  entityType: EntityType | '',
  category: string,
  personaVerified = false,
): DocumentSlot[] {
  if (!entityType) {
    return [];
  }
  const base = ENTITY_DOCUMENTS[entityType];
  const extras = LOB_DOCUMENTS.filter((item) => item.categories.includes(category)).map((item) => item.slot);
  const slots = [...base, ...extras];
  if (!personaVerified) {
    return slots;
  }
  return slots.filter((slot) => !PERSONA_SLOTS.has(slot.id));
}
