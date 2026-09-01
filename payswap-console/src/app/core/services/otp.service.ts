import { inject, Injectable, signal } from '@angular/core';
import { Observable, of, tap } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { ApiService } from './api.service';

export type OtpChannel = 'mobile' | 'email';
export type OtpPurpose = 'verification' | 'security_action';

export interface OtpConfig {
  smsProvider: string;
  smsSender: string;
  smsApiDomain: string;
  testMode: boolean;
  testOtp?: string;
  otpCooldownSeconds: number;
  otpExpirySeconds: number;
}

const DEFAULT_CONFIG: OtpConfig = {
  smsProvider: 'kaleyra',
  smsSender: 'PYSWAP',
  smsApiDomain: 'https://api.in.kaleyra.io',
  testMode: false,
  otpCooldownSeconds: 30,
  otpExpirySeconds: 300,
};

@Injectable({ providedIn: 'root' })
export class OtpService {
  private readonly api = inject(ApiService);

  readonly config = signal<OtpConfig>(DEFAULT_CONFIG);

  loadConfig(): Observable<OtpConfig> {
    return this.api.get<OtpConfig>('/merchant/auth/config').pipe(
      tap((cfg) => this.config.set({ ...DEFAULT_CONFIG, ...cfg })),
      catchError(() => {
        this.config.set(DEFAULT_CONFIG);
        return of(DEFAULT_CONFIG);
      }),
    );
  }

  channelDeliveryLabel(channel: OtpChannel): string {
    if (channel === 'mobile') {
      const sender = this.config().smsSender || 'PYSWAP';
      return `SMS from ${sender} via Kaleyra`;
    }
    return 'Email from support@payswap.in';
  }

  channelHint(channel: OtpChannel): string {
    if (channel === 'mobile') {
      return `We sent a 6-digit code by SMS (${this.channelDeliveryLabel(channel)}).`;
    }
    return 'We sent a 6-digit code to your email inbox.';
  }

  testModeHint(): string | null {
    const cfg = this.config();
    if (!cfg.testMode || !cfg.testOtp) {
      return null;
    }
    return `Development mode: you can also use ${cfg.testOtp}.`;
  }

  authFootnote(): string {
    const sender = this.config().smsSender || 'PYSWAP';
    const test = this.testModeHint();
    const base = `Mobile OTP is delivered by Kaleyra SMS (${sender}). Email OTP is sent from support@payswap.in.`;
    return test ? `${base} ${test}` : base;
  }

  resendRegistrationOtp(channel: OtpChannel): Observable<{ otpWait: number }> {
    return this.api
      .postJson<{ otpWait?: number }>('/merchant/auth/register', { action: 'send_otp', channel })
      .pipe(map((res) => ({ otpWait: res.otpWait ?? this.config().otpCooldownSeconds })));
  }

  resendAccountOtp(channel: OtpChannel, purpose: OtpPurpose = 'verification'): Observable<void> {
    return this.api
      .postJson('/merchant/auth/verify', { action: 'send_otp', channel, purpose })
      .pipe(map(() => undefined));
  }

  confirmAccountOtp(
    channel: OtpChannel,
    code: string,
    purpose: OtpPurpose = 'verification',
  ): Observable<{ verified?: boolean }> {
    return this.api.postJson<{ verified?: boolean }>('/merchant/auth/verify', {
      action: 'confirm',
      channel,
      code,
      purpose,
    });
  }

  sendSecurityOtp(channel: OtpChannel): Observable<void> {
    return this.resendAccountOtp(channel, 'security_action');
  }

  confirmSecurityOtp(channel: OtpChannel, code: string): Observable<void> {
    return this.confirmAccountOtp(channel, code, 'security_action').pipe(map(() => undefined));
  }
}
