import { KycApplication, OnboardingStep, RegistryCheck } from '../models/onboarding.models';

/** Registry check succeeded at source (Cashfree / DigiLocker). */
export function registryCheckVerified(check?: RegistryCheck | null): boolean {
  return (check?.status || '').toUpperCase() === 'VALID';
}

/**
 * Admin returned the application for correction on this wizard step —
 * merchant may run live verification again.
 */
export function adminAllowsReverification(
  app: KycApplication | null | undefined,
  step: OnboardingStep,
): boolean {
  if (!app?.returnReason || app.status !== 'draft') {
    return false;
  }
  const steps = app.correctionSteps ?? [];
  return steps.length === 0 || steps.includes(step);
}

/**
 * After a successful verification API response, hide the verify control.
 * Re-shows only when admin rejects or requests reverification on that step.
 */
export function isVerificationLocked(
  verified: boolean,
  app: KycApplication | null | undefined,
  step: OnboardingStep,
): boolean {
  if (!verified) {
    return false;
  }
  return !adminAllowsReverification(app, step);
}
