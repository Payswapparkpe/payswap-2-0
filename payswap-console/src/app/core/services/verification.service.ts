import { Injectable } from '@angular/core';
import { delay, Observable, of } from 'rxjs';
import { panEntityHint } from '../models/onboarding.models';

/** Shared envelope used by the identity / KYB verification APIs (server-side when live). */
export interface VerificationEnvelope {
  verificationId: string;
  referenceId: number;
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
}

export interface PanVerifyResult extends VerificationEnvelope {
  status: 'VALID' | 'INVALID';
  pan: string;
  registeredName: string;
  panType: string;
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

export interface GstinVerifyResult extends VerificationEnvelope {
  valid: boolean;
  gstin: string;
  legalName: string;
  taxpayerType: string;
  gstinStatus: string;
}

export interface CinVerifyResult extends VerificationEnvelope {
  status: 'VALID' | 'INVALID';
  cin: string;
  companyName: string;
  dateOfIncorporation: string;
  companyStatus: string;
}

export interface BankVerifyResult extends VerificationEnvelope {
  status: 'matched' | 'mismatch';
  accountNumber: string;
  matchedName: string;
}

export interface IfscVerifyResult {
  bankName: string;
  branch: string;
  ifsc: string;
}

let refSeq = 41000;

function envelope(): VerificationEnvelope {
  refSeq += 1;
  return {
    verificationId: `ver_${crypto.randomUUID().slice(0, 8)}`,
    referenceId: refSeq,
  };
}

/**
 * Mock identity / KYB verification client.
 * Live integration will call the same methods from the backend; do not invoke provider APIs from the browser.
 */
@Injectable({ providedIn: 'root' })
export class VerificationService {
  verifyDigilockerAccount(mobile: string, pan: string): Observable<DigilockerAccountResult> {
    const missing = pan.toUpperCase().endsWith('9');
    const status: DigilockerAccountResult['status'] = missing ? 'ACCOUNT_NOT_FOUND' : 'ACCOUNT_EXISTS';
    return of({
      ...envelope(),
      mobile,
      status,
      digilockerId: missing ? undefined : crypto.randomUUID(),
    }).pipe(delay(700));
  }

  createDigilockerUrl(verificationId: string): Observable<DigilockerUrlResult> {
    const result: DigilockerUrlResult = {
      verificationId,
      referenceId: refSeq,
      status: 'PENDING',
      url: `https://digilocker.gov.in/consent/${verificationId}`,
      documentRequested: ['AADHAAR', 'PAN', 'DRIVING_LICENSE'],
    };
    return of(result).pipe(delay(500));
  }

  getDigilockerStatus(verificationId: string, pan: string, name: string): Observable<DigilockerStatusResult> {
    const failed = pan.toUpperCase().endsWith('9');
    const status: DigilockerStatusResult['status'] = failed ? 'FAILED' : 'AUTHENTICATED';
    const documents: DigilockerDocument[] = failed
      ? []
      : [
          { type: 'PAN', name, idMasked: maskId(pan) },
          { type: 'AADHAAR', name, idMasked: 'XXXXXXXX1234' },
          { type: 'DRIVING_LICENSE', name, idMasked: 'KA01********1234' },
        ];
    return of({
      verificationId,
      referenceId: refSeq,
      status,
      documents,
    }).pipe(delay(900));
  }

  verifyPan(pan: string): Observable<PanVerifyResult> {
    const clean = pan.toUpperCase();
    const invalid = clean.endsWith('0');
    const hint = panEntityHint(clean);
    const names: Record<string, string> = {
      P: 'Priya Sharma',
      C: 'Acme Technologies Private Limited',
      F: 'Acme Trading Partners',
      L: 'Acme Commerce LLP',
      T: 'Acme Welfare Trust',
      H: 'Sharma HUF',
    };
    const status: PanVerifyResult['status'] = invalid ? 'INVALID' : 'VALID';
    return of({
      ...envelope(),
      pan: clean,
      status,
      registeredName: names[clean.charAt(3)] ?? 'Fetched Legal Entity',
      panType: hint ?? 'unknown',
    }).pipe(delay(800));
  }

  lookupGstinsByPan(pan: string): Observable<GstinListResult> {
    const clean = pan.toUpperCase();
    const empty = clean.endsWith('1');
    const legal =
      clean.charAt(3) === 'P' ? 'Priya Sharma' : 'Acme Technologies Private Limited';
    const gstins = empty
      ? []
      : [
          { gstin: `29${clean}1Z5`, state: 'Karnataka', status: 'Active', legalName: legal },
          { gstin: `27${clean}1Z2`, state: 'Maharashtra', status: 'Active', legalName: legal },
        ];
    return of({
      ...envelope(),
      pan: clean,
      gstins,
    }).pipe(delay(700));
  }

  verifyGstin(gstin: string): Observable<GstinVerifyResult> {
    const clean = gstin.toUpperCase();
    const valid = !clean.endsWith('0');
    return of({
      ...envelope(),
      gstin: clean,
      valid,
      legalName: valid ? 'Acme Technologies Private Limited' : '',
      taxpayerType: 'Regular',
      gstinStatus: valid ? 'Active' : 'Cancelled',
    }).pipe(delay(850));
  }

  verifyCin(cin: string): Observable<CinVerifyResult> {
    const clean = cin.toUpperCase();
    const valid = clean.length >= 8 && !clean.endsWith('0');
    const status: CinVerifyResult['status'] = valid ? 'VALID' : 'INVALID';
    return of({
      ...envelope(),
      cin: clean,
      status,
      companyName: valid ? 'Acme Technologies Private Limited' : '',
      dateOfIncorporation: '2019-04-12',
      companyStatus: valid ? 'Active' : 'Strike Off',
    }).pipe(delay(850));
  }

  verifyBankAccount(accountNumber: string, holderName: string): Observable<BankVerifyResult> {
    const mismatch = accountNumber.trim().endsWith('0');
    const status: BankVerifyResult['status'] = mismatch ? 'mismatch' : 'matched';
    return of({
      ...envelope(),
      accountNumber,
      status,
      matchedName: mismatch ? 'DOES NOT MATCH' : holderName,
    }).pipe(delay(1100));
  }

  verifyIfsc(code: string): Observable<IfscVerifyResult> {
    const ifsc = code.toUpperCase();
    const map: Record<string, { bankName: string; branch: string }> = {
      HDFC0001234: { bankName: 'HDFC Bank', branch: 'Koramangala, Bengaluru' },
      SBIN0000456: { bankName: 'State Bank of India', branch: 'Connaught Place, New Delhi' },
      ICIC0000789: { bankName: 'ICICI Bank', branch: 'Bandra Kurla Complex, Mumbai' },
    };
    if (map[ifsc]) {
      return of({ ifsc, ...map[ifsc] }).pipe(delay(450));
    }
    const prefix = ifsc.slice(0, 4);
    const banks: Record<string, string> = {
      HDFC: 'HDFC Bank',
      SBIN: 'State Bank of India',
      ICIC: 'ICICI Bank',
      UTIB: 'Axis Bank',
      KKBK: 'Kotak Mahindra Bank',
      YESB: 'Yes Bank',
    };
    return of({
      ifsc,
      bankName: banks[prefix] ?? `${prefix} Bank`,
      branch: 'Main branch',
    }).pipe(delay(450));
  }
}

function maskId(value: string): string {
  if (value.length < 4) {
    return 'XXXX';
  }
  return `${'X'.repeat(value.length - 4)}${value.slice(-4)}`;
}
