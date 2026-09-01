import { Injectable, inject } from '@angular/core';
import { Observable, last, map, switchMap, take, takeWhile, timer } from 'rxjs';
import { ApiService } from './api.service';

/** Shared envelope used by the identity / KYB verification APIs (server-side when live). */
export interface VerificationEnvelope {
  verificationId: string;
  referenceId: number;
  publicId?: string;
}

export interface DigilockerAccountResult extends VerificationEnvelope {
  status: 'ACCOUNT_EXISTS' | 'ACCOUNT_NOT_FOUND';
  mobile: string;
  digilockerId?: string;
}

export interface DigilockerUrlResult extends VerificationEnvelope {
  status: 'PENDING';
  url: string;
  documentRequested: Array<'AADHAAR' | 'PAN' | 'DRIVING_LICENSE'>;
}

export interface DigilockerDocument {
  type: 'AADHAAR' | 'PAN' | 'DRIVING_LICENSE';
  name: string;
  idMasked: string;
}

export interface DigilockerStatusResult extends VerificationEnvelope {
  status: 'PENDING' | 'AUTHENTICATED' | 'FAILED';
  documents: DigilockerDocument[];
  userDetails?: {
    name: string;
    dob: string;
    mobile: string;
    gender: string;
  };
}

export interface PanVerifyResult extends VerificationEnvelope {
  status: 'VALID' | 'INVALID';
  pan: string;
  registeredName: string;
  panType: string;
  dateOfBirth?: string;
  incorporationDate?: string;
  email?: string;
  mobile?: string;
  aadhaarLinked?: boolean;
  address?: { line1: string; line2: string; city: string; state: string; pin: string };
  nameMatch?: string;
  nameMatchWarning?: boolean;
}

export interface GstinVerifyResult extends VerificationEnvelope {
  valid: boolean;
  gstin: string;
  legalName: string;
  taxpayerType: string;
  gstinStatus: string;
  constitutionOfBusiness?: string;
  dateOfRegistration?: string;
  principalPlaceAddress?: string;
  address?: { line1: string; line2: string; city: string; state: string; pin: string };
  natureOfBusinessActivities?: string[];
  stateJurisdiction?: string;
  centerJurisdiction?: string;
}

export interface UdyamVerifyResult extends VerificationEnvelope {
  valid: boolean;
  status: 'VALID' | 'INVALID';
  udyam: string;
  enterpriseName: string;
  ownerName: string;
  organizationType?: string;
  enterpriseType?: string;
  majorActivity?: string;
  dateOfUdyamRegistration?: string;
  dateOfIncorporation?: string;
  dateOfCommencement?: string;
  address?: { line1: string; line2: string; city: string; state: string; pin: string };
  ownerNameMatchWarning?: boolean;
  nicCodes?: Array<{
    serialNumber: string;
    nic2Digit: string;
    nic4Digit: string;
    nic5Digit: string;
    activity: string;
  }>;
}

export interface CinVerifyResult extends VerificationEnvelope {
  status: 'VALID' | 'INVALID';
  cin: string;
  companyName: string;
  dateOfIncorporation: string;
  companyStatus: string;
  companyEmail?: string;
  registeredAddress?: { line1: string; line2: string; city: string; state: string; pin: string };
  directors?: RegistryDirector[];
}

export interface RegistryDirector {
  name: string;
  din: string;
  designation: string;
  dob: string;
  address: string;
  pan: string;
  mobile?: string;
  digiConsent?: boolean;
  kycVerified?: boolean;
  kycPath?: 'digilocker';
}

export interface GstinOptionResult extends VerificationEnvelope {
  gstin: string;
  state: string;
  status: string;
  legalName: string;
}

export interface GstinListResult extends VerificationEnvelope {
  pan: string;
  gstins: Array<Omit<GstinOptionResult, 'verificationId' | 'referenceId'>>;
}

export interface BankVerifyResult extends VerificationEnvelope {
  status: 'matched' | 'mismatch';
  accountNumber: string;
  matchedName: string;
  expectedName?: string;
  nameMatchCategory?: string;
  nameMatchScore?: number;
}

export interface IfscVerifyResult extends VerificationEnvelope {
  bankName: string;
  branch: string;
  ifsc: string;
  status?: string;
}

export interface NameAlignmentCheck {
  kind: string;
  left: string;
  right: string;
  category: string;
  score: number;
  ok: boolean;
}

export interface NameAlignmentResult {
  ok: boolean;
  entityType: string;
  expectedBankName: string;
  checks: NameAlignmentCheck[];
  issues: string[];
  names: {
    pan: string;
    aadhaar: string;
    bank: string;
  };
}

type VerificationAction = 'check' | 'start' | 'sync' | 'validate';

/**
 * Cashfree Secure ID verification client — all provider calls go through Django.
 */
@Injectable({ providedIn: 'root' })
export class VerificationService {
  private readonly api = inject(ApiService);

  private post<T>(body: Record<string, unknown>): Observable<T> {
    return this.api.postJson<T>('/merchant/verification/', body);
  }

  verifyPan(pan: string, name = ''): Observable<PanVerifyResult> {
    return this.post<PanVerifyResult>({
      action: 'check',
      kind: 'pan',
      pan: pan.toUpperCase(),
      name,
    });
  }

  lookupGstinsByPan(pan: string): Observable<GstinListResult> {
    return this.post<GstinListResult>({
      action: 'check',
      kind: 'pan_gstin_list',
      pan: pan.toUpperCase(),
    });
  }

  verifyGstin(gstin: string): Observable<GstinVerifyResult> {
    return this.post<GstinVerifyResult>({
      action: 'check',
      kind: 'gstin',
      gstin: gstin.toUpperCase(),
    });
  }

  verifyCin(cin: string): Observable<CinVerifyResult> {
    return this.post<CinVerifyResult>({
      action: 'check',
      kind: 'cin',
      cin: cin.toUpperCase(),
    });
  }

  verifyUdyam(udyam: string, ownerName = ''): Observable<UdyamVerifyResult> {
    return this.post<UdyamVerifyResult>({
      action: 'check',
      kind: 'udyam',
      udyam: udyam.toUpperCase(),
      ownerName,
    });
  }

  verifyBankAccount(accountNumber: string, holderName: string, ifsc = ''): Observable<BankVerifyResult> {
    return this.post<BankVerifyResult>({
      action: 'check',
      kind: 'bank',
      accountNumber,
      holderName,
      name: holderName,
      ifsc: ifsc.toUpperCase(),
    });
  }

  verifyIfsc(code: string): Observable<IfscVerifyResult> {
    return this.post<IfscVerifyResult>({
      action: 'check',
      kind: 'ifsc',
      ifsc: code.toUpperCase(),
    });
  }

  verifyDigilockerAccount(mobile: string, pan: string): Observable<DigilockerAccountResult> {
    return this.post<DigilockerAccountResult>({
      action: 'check',
      kind: 'digilocker_account',
      mobile,
      pan: pan.toUpperCase(),
    });
  }

  createDigilockerUrl(redirectUrl?: string): Observable<DigilockerUrlResult> {
    const redirect =
      redirectUrl ||
      (typeof window !== 'undefined' && window.location.origin.startsWith('https://')
        ? `${window.location.origin}/digilocker-return`
        : '');
    return this.post<DigilockerUrlResult>({
      action: 'start',
      kind: 'digilocker',
      ...(redirect ? { redirectUrl: redirect } : {}),
    });
  }

  getDigilockerStatus(verificationId: string, _pan?: string, _name?: string): Observable<DigilockerStatusResult> {
    return this.post<DigilockerStatusResult>({
      action: 'sync',
      kind: 'digilocker',
      verificationId,
    });
  }

  /** Poll Cashfree until consent completes or times out (~2 min). */
  pollDigilockerStatus(
    verificationId: string,
    pan?: string,
    name?: string,
    maxAttempts = 40,
    intervalMs = 3000,
  ): Observable<DigilockerStatusResult> {
    return timer(0, intervalMs).pipe(
      take(maxAttempts),
      switchMap(() => this.getDigilockerStatus(verificationId, pan, name)),
      takeWhile((status) => status.status === 'PENDING', true),
      last(),
      map((status) => {
        if (status.status === 'PENDING') {
          throw new Error(
            'DigiLocker consent is still pending. Finish consent in the opened tab, then click verify again.',
          );
        }
        return status;
      }),
    );
  }

  validateNameAlignment(): Observable<NameAlignmentResult> {
    return this.post<NameAlignmentResult>({
      action: 'validate',
      kind: 'alignment',
    });
  }

  getStatus(): Observable<{
    kycStatus: string;
    kybStatus: string;
    bankStatus: string;
    agreementStatus: string;
    commercialStatus: string;
    nameAlignment: NameAlignmentResult;
  }> {
    return this.api.get('/merchant/verification/');
  }
}
