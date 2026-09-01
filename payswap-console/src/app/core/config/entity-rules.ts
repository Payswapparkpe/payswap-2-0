import { EntityType, KycApplication, OnboardingStep } from '../models/onboarding.models';

export type GstMode = 'hidden' | 'optional';
export type BankMatches = 'person' | 'entity';
export type AllowedAccountType = 'current' | 'savings';

export interface EntityOnboardingRules {
  needsKybStep: boolean;
  needsCin: boolean;
  needsLlpin: boolean;
  needsDoi: boolean;
  needsBusinessPan: boolean;
  /** Registered office comes from CIN; otherwise user enters manually on KYB. */
  addressFromCin: boolean;
  needsUdyam: boolean;
  /** Partnership / NGO: manual partner-trustee list + optional deed OCR. */
  needsPartnerRegistry: boolean;
  gst: GstMode;
  needsUbo: boolean;
  uboThreshold: number;
  canSignatoryDifferFromOwner: boolean;
  needsAuthorisationInstrument: boolean;
  lightProfile: boolean;
  businessPanLabel: string;
  bankHolderHint: string;
  bankMatches: BankMatches;
  allowedAccountTypes: AllowedAccountType[];
}

export const ENTITY_RULES: Record<EntityType, EntityOnboardingRules> = {
  individual: {
    needsKybStep: false,
    needsCin: false,
    needsLlpin: false,
    needsDoi: false,
    needsBusinessPan: false,
    addressFromCin: false,
    needsUdyam: true,
    needsPartnerRegistry: false,
    gst: 'hidden',
    needsUbo: false,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: false,
    needsAuthorisationInstrument: false,
    lightProfile: true,
    businessPanLabel: '',
    bankHolderHint: 'Account holder name must match the verified individual — savings or current account.',
    bankMatches: 'person',
    allowedAccountTypes: ['current', 'savings'],
  },
  proprietorship: {
    needsKybStep: true,
    needsCin: false,
    needsLlpin: false,
    needsDoi: false,
    needsBusinessPan: false,
    addressFromCin: false,
    needsUdyam: false,
    needsPartnerRegistry: false,
    gst: 'optional',
    needsUbo: false,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: false,
    needsAuthorisationInstrument: false,
    lightProfile: false,
    businessPanLabel: '',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountTypes: ['current'],
  },
  partnership: {
    needsKybStep: true,
    needsCin: false,
    needsLlpin: false,
    needsDoi: true,
    needsBusinessPan: true,
    addressFromCin: false,
    needsUdyam: false,
    needsPartnerRegistry: true,
    gst: 'optional',
    needsUbo: true,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: true,
    needsAuthorisationInstrument: true,
    lightProfile: false,
    businessPanLabel: 'Partnership firm PAN',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountTypes: ['current'],
  },
  llp: {
    needsKybStep: true,
    needsCin: false,
    needsLlpin: true,
    needsDoi: true,
    needsBusinessPan: false,
    addressFromCin: false,
    needsUdyam: false,
    needsPartnerRegistry: false,
    gst: 'optional',
    needsUbo: true,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: true,
    needsAuthorisationInstrument: true,
    lightProfile: false,
    businessPanLabel: '',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountTypes: ['current'],
  },
  private_limited: {
    needsKybStep: true,
    needsCin: true,
    needsLlpin: false,
    needsDoi: true,
    needsBusinessPan: true,
    addressFromCin: true,
    needsUdyam: false,
    needsPartnerRegistry: false,
    gst: 'optional',
    needsUbo: true,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: true,
    needsAuthorisationInstrument: true,
    lightProfile: false,
    businessPanLabel: 'Company PAN',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountTypes: ['current'],
  },
  public_limited: {
    needsKybStep: true,
    needsCin: true,
    needsLlpin: false,
    needsDoi: true,
    needsBusinessPan: true,
    addressFromCin: true,
    needsUdyam: false,
    needsPartnerRegistry: false,
    gst: 'optional',
    needsUbo: true,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: true,
    needsAuthorisationInstrument: true,
    lightProfile: false,
    businessPanLabel: 'Company PAN',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountTypes: ['current'],
  },
  opc: {
    needsKybStep: true,
    needsCin: true,
    needsLlpin: false,
    needsDoi: true,
    needsBusinessPan: false,
    addressFromCin: true,
    needsUdyam: false,
    needsPartnerRegistry: false,
    gst: 'optional',
    needsUbo: true,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: true,
    needsAuthorisationInstrument: true,
    lightProfile: false,
    businessPanLabel: '',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountTypes: ['current'],
  },
  trust_society_ngo: {
    needsKybStep: true,
    needsCin: false,
    needsLlpin: false,
    needsDoi: true,
    needsBusinessPan: false,
    addressFromCin: false,
    needsUdyam: false,
    needsPartnerRegistry: true,
    gst: 'optional',
    needsUbo: true,
    uboThreshold: 15,
    canSignatoryDifferFromOwner: true,
    needsAuthorisationInstrument: true,
    lightProfile: false,
    businessPanLabel: '',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountTypes: ['current'],
  },
  huf: {
    needsKybStep: true,
    needsCin: false,
    needsLlpin: false,
    needsDoi: false,
    needsBusinessPan: false,
    addressFromCin: false,
    needsUdyam: false,
    needsPartnerRegistry: false,
    gst: 'optional',
    needsUbo: false,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: false,
    needsAuthorisationInstrument: false,
    lightProfile: false,
    businessPanLabel: '',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountTypes: ['current'],
  },
};

export function rulesFor(entityType: EntityType | ''): EntityOnboardingRules | null {
  return entityType ? ENTITY_RULES[entityType] : null;
}

export const CANONICAL_ONBOARDING_STEPS: { id: OnboardingStep; label: string }[] = [
  { id: 'signatory', label: 'KYC' },
  { id: 'profile', label: 'Business' },
  { id: 'auth_signatory', label: 'Auth signatory KYC' },
  { id: 'owner', label: 'Owner KYC' },
  { id: 'identity', label: 'KYB' },
  { id: 'ubo', label: 'Owners' },
  { id: 'bank', label: 'Bank' },
  { id: 'documents', label: 'Documents' },
  { id: 'review', label: 'Review' },
];

const DIRECTOR_RELATIONS = new Set([
  'director',
  'managing_director',
  'whole_time_director',
  'designated_partner',
  'partner',
  'trustee',
  'karta',
  'proprietor',
]);

export function isDirectorRelation(relation: string): boolean {
  return DIRECTOR_RELATIONS.has(relation);
}

export function needsAuthSignatoryPersonKyc(app: KycApplication): boolean {
  return app.kycPersonIsAuthorisedSignatory === false;
}

/** Opener holds a directorship/partnership role — KYB needs auth instrument, not repeat opener KYC. */
export function openerIsPrincipal(app: KycApplication): boolean {
  return isDirectorRelation(app.signatoryRelation) && app.kycPersonIsAuthorisedSignatory !== false;
}

export function stepsForEntity(
  entityType: EntityType | '',
  signatoryIsOwner: boolean | null = null,
  kycPersonIsAuthorisedSignatory: boolean | null = null,
): { id: OnboardingStep; label: string }[] {
  if (!entityType) {
    return CANONICAL_ONBOARDING_STEPS.filter((step) => step.id === 'signatory' || step.id === 'profile');
  }
  const rules = ENTITY_RULES[entityType];
  return CANONICAL_ONBOARDING_STEPS.filter((step) => {
    if (step.id === 'auth_signatory') {
      return kycPersonIsAuthorisedSignatory === false;
    }
    if (step.id === 'owner') {
      return rules.canSignatoryDifferFromOwner && signatoryIsOwner === false;
    }
    if (step.id === 'identity') {
      return rules.needsKybStep;
    }
    if (step.id === 'ubo') {
      return rules.needsUbo;
    }
    return true;
  });
}

export function stepsForApplication(app: KycApplication): { id: OnboardingStep; label: string }[] {
  return stepsForEntity(app.profile.entityType, app.signatoryIsOwner, app.kycPersonIsAuthorisedSignatory);
}

export function onboardingNav(app: KycApplication) {
  return {
    next: (from: OnboardingStep) =>
      nextOnboardingStep(from, app.profile.entityType, app.signatoryIsOwner, app.kycPersonIsAuthorisedSignatory),
    prev: (from: OnboardingStep) =>
      prevOnboardingStep(from, app.profile.entityType, app.signatoryIsOwner, app.kycPersonIsAuthorisedSignatory),
  };
}

export function nextOnboardingStep(
  from: OnboardingStep,
  entityType: EntityType | '',
  signatoryIsOwner: boolean | null = null,
  kycPersonIsAuthorisedSignatory: boolean | null = null,
): OnboardingStep {
  const steps = stepsForEntity(entityType, signatoryIsOwner, kycPersonIsAuthorisedSignatory);
  const index = steps.findIndex((step) => step.id === from);
  if (index < 0) {
    return steps[0]?.id ?? 'signatory';
  }
  return steps[Math.min(index + 1, steps.length - 1)].id;
}

export function prevOnboardingStep(
  from: OnboardingStep,
  entityType: EntityType | '',
  signatoryIsOwner: boolean | null = null,
  kycPersonIsAuthorisedSignatory: boolean | null = null,
): OnboardingStep {
  const steps = stepsForEntity(entityType, signatoryIsOwner, kycPersonIsAuthorisedSignatory);
  const index = steps.findIndex((step) => step.id === from);
  if (index <= 0) {
    return steps[0]?.id ?? 'signatory';
  }
  return steps[index - 1].id;
}

export function allowedAccountTypes(entityType: EntityType | ''): AllowedAccountType[] {
  return rulesFor(entityType)?.allowedAccountTypes ?? ['current'];
}

/** Default account type when the entity allows only one option. */
export function allowedAccountType(entityType: EntityType | ''): AllowedAccountType {
  return allowedAccountTypes(entityType)[0] ?? 'current';
}

export function isAllowedAccountType(entityType: EntityType | '', type: AllowedAccountType): boolean {
  return allowedAccountTypes(entityType).includes(type);
}

export function requiresUbo(entityType: EntityType | ''): boolean {
  return !!rulesFor(entityType)?.needsUbo;
}

export function uboThreshold(entityType: EntityType | ''): number {
  return rulesFor(entityType)?.uboThreshold ?? 10;
}

export function resolvedSignatoryIsOwner(app: KycApplication): boolean {
  const rules = rulesFor(app.profile.entityType);
  if (!rules || !rules.canSignatoryDifferFromOwner) {
    return true;
  }
  return app.signatoryIsOwner === true;
}

export function needsOwnerPersonKyc(app: KycApplication): boolean {
  const rules = rulesFor(app.profile.entityType);
  return !!rules?.canSignatoryDifferFromOwner && app.signatoryIsOwner === false;
}

export function authorisationSlotId(entityType: EntityType | ''): string | null {
  if (!entityType || !rulesFor(entityType)?.needsAuthorisationInstrument) {
    return null;
  }
  if (entityType === 'partnership') {
    return 'auth_letter';
  }
  if (entityType === 'trust_society_ngo') {
    return 'trustee_resolution';
  }
  return 'board_resolution';
}

export function enforcePersonaKycFirst(app: KycApplication): KycApplication {
  if (!app.signatory.verified) {
    return app.currentStep === 'signatory' ? app : { ...app, currentStep: 'signatory' };
  }
  const allowed = stepsForEntity(app.profile.entityType, app.signatoryIsOwner, app.kycPersonIsAuthorisedSignatory).map(
    (step) => step.id,
  );
  if (allowed.includes(app.currentStep)) {
    return app;
  }
  const order = CANONICAL_ONBOARDING_STEPS.map((step) => step.id);
  const start = Math.max(order.indexOf(app.currentStep), 0);
  for (let i = start; i < order.length; i++) {
    if (allowed.includes(order[i])) {
      return { ...app, currentStep: order[i] };
    }
  }
  return { ...app, currentStep: 'profile' };
}
