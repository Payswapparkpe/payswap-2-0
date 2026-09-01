import { EntityType } from '../models/onboarding.models';

export interface DocumentSlot {
  id: string;
  label: string;
  hint: string;
  required: boolean;
  accept: string;
}

const ACCEPT = '.pdf,.jpg,.jpeg,.png';

const MOA: DocumentSlot = {
  id: 'moa',
  label: 'Memorandum of Association (MOA)',
  hint: 'Certified copy of MOA.',
  required: true,
  accept: ACCEPT,
};

const AOA: DocumentSlot = {
  id: 'aoa',
  label: 'Articles of Association (AOA)',
  hint: 'Certified copy of AOA.',
  required: true,
  accept: ACCEPT,
};

const BOR: DocumentSlot = {
  id: 'board_resolution',
  label: 'Board Resolution (BOR)',
  hint: 'Certified board resolution appointing the authorised signatory.',
  required: true,
  accept: ACCEPT,
};

const AUTH_LETTER: DocumentSlot = {
  id: 'auth_letter',
  label: 'Letter of authority / partnership authorisation',
  hint: 'Signed letter appointing the authorised signatory for this Payswap account.',
  required: true,
  accept: ACCEPT,
};

const TRUSTEE_RESOLUTION: DocumentSlot = {
  id: 'trustee_resolution',
  label: 'Trustee / governing body resolution',
  hint: 'Resolution authorising the signatory to operate this Payswap account.',
  required: true,
  accept: ACCEPT,
};

const PARTNERSHIP_DEED: DocumentSlot = {
  id: 'partnership_deed',
  label: 'Partnership deed (optional)',
  hint: 'Upload to auto-extract partner names via OCR, or add partners manually below.',
  required: false,
  accept: ACCEPT,
};

const TRUST_DEED: DocumentSlot = {
  id: 'trust_deed',
  label: 'Trust / society deed (optional)',
  hint: 'Upload to auto-extract trustee names via OCR, or add trustees manually below.',
  required: false,
  accept: ACCEPT,
};

const BANK_PROOF: DocumentSlot = {
  id: 'bank_proof',
  label: 'Cancelled cheque / bank statement',
  hint: 'Current account in the entity name. Collected on the bank step.',
  required: true,
  accept: ACCEPT,
};

/** Physical KYB uploads for companies — MOA, AOA, and BOR only. */
export const CORPORATE_KYB_DOCUMENTS: DocumentSlot[] = [MOA, AOA, BOR];

const LLP_BOR: DocumentSlot = {
  ...BOR,
  hint: 'Certified resolution appointing the authorised signatory for this Payswap account.',
};

export const ENTITY_DOCUMENTS: Record<EntityType, DocumentSlot[]> = {
  individual: [BANK_PROOF],
  proprietorship: [BANK_PROOF],
  partnership: [AUTH_LETTER, BANK_PROOF],
  llp: [LLP_BOR, BANK_PROOF],
  private_limited: [...CORPORATE_KYB_DOCUMENTS, BANK_PROOF],
  public_limited: [...CORPORATE_KYB_DOCUMENTS, BANK_PROOF],
  opc: [...CORPORATE_KYB_DOCUMENTS, BANK_PROOF],
  trust_society_ngo: [TRUSTEE_RESOLUTION, BANK_PROOF],
  huf: [BANK_PROOF],
};

const BANK_SLOTS = new Set(['bank_proof']);

const CORPORATE_ENTITY_TYPES = new Set<EntityType>(['private_limited', 'public_limited', 'opc']);

/** MOA, AOA, BOR, auth instruments, and optional registry deeds on the KYB step. */
export function kybPhysicalDocuments(
  entityType: EntityType | '',
  _category = '',
  _gstinProvided = false,
): DocumentSlot[] {
  if (CORPORATE_ENTITY_TYPES.has(entityType as EntityType)) {
    return [...CORPORATE_KYB_DOCUMENTS];
  }
  if (entityType === 'llp') {
    return [LLP_BOR];
  }
  if (entityType === 'partnership') {
    return [AUTH_LETTER, PARTNERSHIP_DEED];
  }
  if (entityType === 'trust_society_ngo') {
    return [TRUSTEE_RESOLUTION, TRUST_DEED];
  }
  return [];
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
  _category = '',
  _personaVerified = false,
): DocumentSlot[] {
  if (!entityType) {
    return [];
  }
  return [...ENTITY_DOCUMENTS[entityType]];
}

export function registryDeedSlotId(entityType: EntityType | ''): string | null {
  if (entityType === 'partnership') {
    return 'partnership_deed';
  }
  if (entityType === 'trust_society_ngo') {
    return 'trust_deed';
  }
  return null;
}
