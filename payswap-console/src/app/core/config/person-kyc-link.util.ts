import { KycApplication, RegistryDirector, SignatoryKyc } from '../models/onboarding.models';

export type PersonKycLinkSource = 'signatory' | 'owner' | 'auth_signatory';

function normalizeName(value: string): string {
  return value.trim().replace(/\s+/g, ' ').toLowerCase();
}

function normalizePan(value: string): string {
  return value.trim().toUpperCase();
}

/** Match a verified person to an MCA director row by PAN, else normalized name. */
export function personMatchesDirector(
  person: Pick<SignatoryKyc, 'name' | 'pan'>,
  director: Pick<RegistryDirector, 'name' | 'pan'>,
): boolean {
  const personPan = normalizePan(person.pan || '');
  const directorPan = normalizePan(director.pan || '');
  if (personPan && directorPan && personPan === directorPan) {
    return true;
  }
  const personName = normalizeName(person.name || '');
  const directorName = normalizeName(director.name || '');
  return !!personName && !!directorName && personName === directorName;
}

export function applyVerifiedPersonToDirectors(
  directors: RegistryDirector[],
  person: SignatoryKyc | null | undefined,
  source: PersonKycLinkSource,
): RegistryDirector[] {
  if (!person?.verified || !directors.length) {
    return directors;
  }
  return directors.map((director) => {
    if (director.kycVerified) {
      return director;
    }
    if (!personMatchesDirector(person, director)) {
      return director;
    }
    return {
      ...director,
      pan: normalizePan(director.pan || person.pan),
      mobile: director.mobile || person.mobile,
      kycVerified: true,
      kycPath: 'digilocker',
      kycLinkedFrom: source,
      digilocker: person.digilocker ?? director.digilocker,
    };
  });
}

/** Reuse account / owner DigiLocker KYC on matching MCA director rows. */
export function syncDirectorsFromApplication(
  directors: RegistryDirector[],
  application: Pick<KycApplication, 'signatory' | 'ownerKyc' | 'signatoryIsOwner'>,
): RegistryDirector[] {
  let next = applyVerifiedPersonToDirectors(directors, application.signatory, 'signatory');
  if (application.signatoryIsOwner === false && application.ownerKyc?.verified) {
    next = applyVerifiedPersonToDirectors(next, application.ownerKyc, 'owner');
  }
  return next;
}

export function directorKycLinkedFrom(director: RegistryDirector): PersonKycLinkSource | null {
  return director.kycLinkedFrom ?? null;
}
