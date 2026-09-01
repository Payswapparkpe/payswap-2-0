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
  gst: GstMode;
  needsUbo: boolean;
  uboThreshold: number;
  canSignatoryDifferFromOwner: boolean;
  needsAuthorisationInstrument: boolean;
  lightProfile: boolean;
  businessPanLabel: string;
  bankHolderHint: string;
  bankMatches: BankMatches;
  allowedAccountType: AllowedAccountType;
}

export const ENTITY_RULES: Record<EntityType, EntityOnboardingRules> = {
  individual: {
    needsKybStep: false,
    needsCin: false,
    needsLlpin: false,
    needsDoi: false,
    needsBusinessPan: false,
    gst: 'hidden',
    needsUbo: false,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: false,
    needsAuthorisationInstrument: false,
    lightProfile: true,
    businessPanLabel: '',
    bankHolderHint: 'Account holder name must match the entity name on the savings account (the verified individual).',
    bankMatches: 'person',
    allowedAccountType: 'savings',
  },
  proprietorship: {
    needsKybStep: true,
    needsCin: false,
    needsLlpin: false,
    needsDoi: false,
    needsBusinessPan: false,
    gst: 'optional',
    needsUbo: false,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: false,
    needsAuthorisationInstrument: false,
    lightProfile: false,
    businessPanLabel: '',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountType: 'current',
  },
  partnership: {
    needsKybStep: true,
    needsCin: false,
    needsLlpin: false,
    needsDoi: true,
    needsBusinessPan: true,
    gst: 'optional',
    needsUbo: true,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: true,
    needsAuthorisationInstrument: true,
    lightProfile: false,
    businessPanLabel: 'Partnership firm PAN',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountType: 'current',
  },
  llp: {
    needsKybStep: true,
    needsCin: false,
    needsLlpin: true,
    needsDoi: true,
    needsBusinessPan: false,
    gst: 'optional',
    needsUbo: true,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: true,
    needsAuthorisationInstrument: true,
    lightProfile: false,
    businessPanLabel: '',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountType: 'current',
  },
  private_limited: {
    needsKybStep: true,
    needsCin: true,
    needsLlpin: false,
    needsDoi: true,
    needsBusinessPan: true,
    gst: 'optional',
    needsUbo: true,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: true,
    needsAuthorisationInstrument: true,
    lightProfile: false,
    businessPanLabel: 'Company PAN',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountType: 'current',
  },
  public_limited: {
    needsKybStep: true,
    needsCin: true,
    needsLlpin: false,
    needsDoi: true,
    needsBusinessPan: true,
    gst: 'optional',
    needsUbo: true,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: true,
    needsAuthorisationInstrument: true,
    lightProfile: false,
    businessPanLabel: 'Company PAN',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountType: 'current',
  },
  opc: {
    needsKybStep: true,
    needsCin: true,
    needsLlpin: false,
    needsDoi: true,
    needsBusinessPan: false,
    gst: 'optional',
    needsUbo: true,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: true,
    needsAuthorisationInstrument: true,
    lightProfile: false,
    businessPanLabel: '',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountType: 'current',
  },
  trust_society_ngo: {
    needsKybStep: true,
    needsCin: false,
    needsLlpin: false,
    needsDoi: true,
    needsBusinessPan: false,
    gst: 'optional',
    needsUbo: true,
    uboThreshold: 15,
    canSignatoryDifferFromOwner: true,
    needsAuthorisationInstrument: true,
    lightProfile: false,
    businessPanLabel: '',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountType: 'current',
  },
  huf: {
    needsKybStep: true,
    needsCin: false,
    needsLlpin: false,
    needsDoi: false,
    needsBusinessPan: false,
    gst: 'optional',
    needsUbo: false,
    uboThreshold: 10,
    canSignatoryDifferFromOwner: false,
    needsAuthorisationInstrument: false,
    lightProfile: false,
    businessPanLabel: '',
    bankHolderHint: 'Current account only. Account holder name must match the entity legal name.',
    bankMatches: 'entity',
    allowedAccountType: 'current',
  },
};

export function rulesFor(entityType: EntityType | ''): EntityOnboardingRules | null {
  return entityType ? ENTITY_RULES[entityType] : null;
}

export const CANONICAL_ONBOARDING_STEPS: { id: OnboardingStep; label: string }[] = [
  { id: 'signatory', label: 'KYC' },
  { id: 'profile', label: 'Business' },
  { id: 'owner', label: 'Owner KYC' },
  { id: 'identity', label: 'KYB' },
  { id: 'ubo', label: 'Owners' },
  { id: 'bank', label: 'Bank' },
  { id: 'documents', label: 'Documents' },
  { id: 'review', label: 'Review' },
];

export function stepsForEntity(
  entityType: EntityType | '',
  signatoryIsOwner: boolean | null = null,
): { id: OnboardingStep; label: string }[] {
  if (!entityType) {
    return CANONICAL_ONBOARDING_STEPS.filter((step) => step.id === 'signatory' || step.id === 'profile');
  }
  const rules = ENTITY_RULES[entityType];
  return CANONICAL_ONBOARDING_STEPS.filter((step) => {
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

export function nextOnboardingStep(
  from: OnboardingStep,
  entityType: EntityType | '',
  signatoryIsOwner: boolean | null = null,
): OnboardingStep {
  const steps = stepsForEntity(entityType, signatoryIsOwner);
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
): OnboardingStep {
  const steps = stepsForEntity(entityType, signatoryIsOwner);
  const index = steps.findIndex((step) => step.id === from);
  if (index <= 0) {
    return steps[0]?.id ?? 'signatory';
  }
  return steps[index - 1].id;
}

export function allowedAccountType(entityType: EntityType | ''): AllowedAccountType {
  return rulesFor(entityType)?.allowedAccountType ?? 'current';
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
  const allowed = stepsForEntity(app.profile.entityType, app.signatoryIsOwner).map((step) => step.id);
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
