import { EntityType } from '../models/onboarding.models';

export type SignatoryRelation =
  | 'self'
  | 'proprietor'
  | 'partner'
  | 'designated_partner'
  | 'director'
  | 'managing_director'
  | 'whole_time_director'
  | 'company_secretary'
  | 'karta'
  | 'trustee'
  | 'authorised_representative';

export const SIGNATORY_RELATION_LABELS: Record<SignatoryRelation, string> = {
  self: 'Self',
  proprietor: 'Proprietor',
  partner: 'Partner',
  designated_partner: 'Designated partner',
  director: 'Director',
  managing_director: 'Managing director',
  whole_time_director: 'Whole-time director',
  company_secretary: 'Company secretary',
  karta: 'Karta',
  trustee: 'Trustee / secretary',
  authorised_representative: 'Authorised representative',
};

const BY_ENTITY: Record<EntityType, SignatoryRelation[]> = {
  individual: ['self'],
  proprietorship: ['proprietor', 'authorised_representative'],
  partnership: ['partner', 'authorised_representative'],
  llp: ['designated_partner', 'partner', 'authorised_representative'],
  private_limited: [
    'director',
    'managing_director',
    'whole_time_director',
    'company_secretary',
    'authorised_representative',
  ],
  public_limited: [
    'director',
    'managing_director',
    'whole_time_director',
    'company_secretary',
    'authorised_representative',
  ],
  opc: ['director', 'authorised_representative'],
  trust_society_ngo: ['trustee', 'authorised_representative'],
  huf: ['karta', 'authorised_representative'],
};

export function relationsFor(entityType: EntityType | ''): { id: SignatoryRelation; label: string }[] {
  const ids = entityType ? BY_ENTITY[entityType] : [];
  return ids.map((id) => ({ id, label: SIGNATORY_RELATION_LABELS[id] }));
}
