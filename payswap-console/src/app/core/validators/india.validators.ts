import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';
import { DEFAULT_MARKET } from '../config/market.config';

export const MOBILE_PATTERN = /^[6-9]\d{9}$/;
export const PAN_PATTERN = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
export const GSTIN_PATTERN = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;
export const IFSC_PATTERN = /^[A-Z]{4}0[A-Z0-9]{6}$/;
export const PIN_PATTERN = /^[1-9][0-9]{5}$/;
export const CIN_PATTERN = /^[UL][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$/;
export const DEMO_OTP = '123456';

export interface MobileValidationConfig {
  pattern: RegExp;
  marketCode: string;
}

export const INDIA_MOBILE_CONFIG: MobileValidationConfig = {
  pattern: MOBILE_PATTERN,
  marketCode: DEFAULT_MARKET.locale,
};

export function mobileWith(config: MobileValidationConfig): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const value = String(control.value ?? '').trim();
    if (!value) {
      return null;
    }
    return config.pattern.test(value) ? null : { mobile: true, market: config.marketCode };
  };
}

export function indianMobile(): ValidatorFn {
  return mobileWith(INDIA_MOBILE_CONFIG);
}

export function pan(): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const value = String(control.value ?? '').trim().toUpperCase();
    if (!value) {
      return null;
    }
    return PAN_PATTERN.test(value) ? null : { pan: true };
  };
}

export function gstin(): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const value = String(control.value ?? '').trim().toUpperCase();
    if (!value) {
      return null;
    }
    return GSTIN_PATTERN.test(value) ? null : { gstin: true };
  };
}

export function ifsc(): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const value = String(control.value ?? '').trim().toUpperCase();
    if (!value) {
      return null;
    }
    return IFSC_PATTERN.test(value) ? null : { ifsc: true };
  };
}

export function pinCode(): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const value = String(control.value ?? '').trim();
    if (!value) {
      return null;
    }
    return PIN_PATTERN.test(value) ? null : { pin: true };
  };
}

export function passwordStrength(): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const value = String(control.value ?? '');
    if (!value) {
      return null;
    }
    const checks = {
      length: value.length >= 8,
      upper: /[A-Z]/.test(value),
      lower: /[a-z]/.test(value),
      number: /\d/.test(value),
      special: /[^A-Za-z0-9]/.test(value),
    };
    const passed = Object.values(checks).filter(Boolean).length;
    return passed === 5 ? null : { passwordStrength: { ...checks, score: passed } };
  };
}

export function passwordScore(value: string): number {
  let score = 0;
  if (value.length >= 8) score += 1;
  if (/[A-Z]/.test(value)) score += 1;
  if (/[a-z]/.test(value)) score += 1;
  if (/\d/.test(value)) score += 1;
  if (/[^A-Za-z0-9]/.test(value)) score += 1;
  return score;
}
