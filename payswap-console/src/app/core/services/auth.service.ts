import { computed, inject, Injectable, signal } from '@angular/core';
import { Observable, catchError, map, of, switchMap, tap } from 'rxjs';
import { User } from '../models/onboarding.models';
import { ApiService } from './api.service';
import { OtpChannel, OtpService } from './otp.service';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = inject(ApiService);
  private readonly otp = inject(OtpService);

  readonly user = signal<User | null>(null);
  readonly registrationPending = signal(false);
  readonly registrationStatus = signal({ emailVerified: false, mobileVerified: false });
  readonly registrationContact = signal({ email: '', mobile: '' });
  readonly isAuthenticated = computed(() => !!this.user());
  readonly isAdmin = computed(() => false);
  readonly isVerified = computed(() => {
    const u = this.user();
    return !!u?.mobileVerified && !!u?.emailVerified;
  });

  hydrate(): Observable<User | null> {
    return this.api.get<{ user: User }>('/merchant/auth/me').pipe(
      map((res) => res.user),
      tap((user) => this.user.set(user)),
      catchError(() => {
        this.user.set(null);
        return of(null);
      }),
    );
  }

  register(payload: {
    fullName: string;
    email: string;
    mobile: string;
    password: string;
    partnerType: 'corporate';
  }): Observable<{ emailVerified: boolean; mobileVerified: boolean }> {
    return this.api
      .postJson<{ emailVerified: boolean; mobileVerified: boolean }>('/merchant/auth/register', {
        action: 'details',
        fullName: payload.fullName,
        email: payload.email,
        mobile: payload.mobile,
        password: payload.password,
        acceptTerms: true,
      })
      .pipe(
        tap((status) => {
          this.registrationContact.set({ email: payload.email, mobile: payload.mobile });
          this.registrationPending.set(true);
          this.registrationStatus.set(status);
        }),
      );
  }

  confirmRegistrationOtp(
    channel: 'mobile' | 'email',
    code: string,
  ): Observable<{ emailVerified: boolean; mobileVerified: boolean }> {
    return this.api.postJson<{ emailVerified: boolean; mobileVerified: boolean }>('/merchant/auth/register', {
      action: 'confirm_otp',
      channel,
      code,
    }).pipe(tap((status) => this.registrationStatus.set(status)));
  }

  finishRegistration(): Observable<User> {
    return this.api
      .postJson<{ user: User }>('/merchant/auth/register', {
        action: 'finish',
        acceptTerms: true,
      })
      .pipe(
        map((res) => res.user),
        tap((user) => {
          this.user.set(user);
          this.registrationPending.set(false);
        }),
      );
  }

  resendRegistrationOtp(channel: OtpChannel): Observable<void> {
    if (this.registrationPending() || !this.user()) {
      return this.otp.resendRegistrationOtp(channel).pipe(map(() => undefined));
    }
    return this.otp.resendAccountOtp(channel).pipe(map(() => undefined));
  }

  private confirmAccountOtp(channel: 'mobile' | 'email', code: string): Observable<User> {
    return this.api.postJson<{ user: User }>('/merchant/auth/verify', { action: 'confirm', channel, code }).pipe(
      map((res) => res.user),
      tap((user) => this.user.set(user)),
    );
  }

  login(identifier: string, password: string): Observable<User> {
    return this.api.postJson<{ user: User }>('/merchant/auth/login', { identifier, password }).pipe(
      map((res) => res.user),
      tap((user) => {
        this.registrationPending.set(false);
        this.user.set(user);
      }),
    );
  }

  verifyOtp(channel: 'mobile' | 'email', code: string): Observable<User> {
    if (this.registrationPending() || !this.user()) {
      return this.confirmRegistrationOtp(channel, code).pipe(
        switchMap((status) => {
          if (status.emailVerified && status.mobileVerified) {
            return this.finishRegistration();
          }
          return this.hydrate().pipe(map((user) => user as User));
        }),
      );
    }
    return this.confirmAccountOtp(channel, code);
  }

  resetPassword(identifier: string): Observable<void> {
    return this.api
      .postJson('/merchant/auth/password-reset', { action: 'request', identifier })
      .pipe(map(() => undefined));
  }

  validatePasswordResetLink(uid: string, token: string): Observable<void> {
    return this.api
      .postJson('/merchant/auth/password-reset', { action: 'validate', uid, token })
      .pipe(map(() => undefined));
  }

  confirmPasswordReset(uid: string, token: string, password: string, confirmPassword: string): Observable<void> {
    return this.api
      .postJson('/merchant/auth/password-reset', {
        action: 'confirm',
        uid,
        token,
        password,
        confirmPassword,
      })
      .pipe(map(() => undefined));
  }

  logout(): Observable<void> {
    return this.api.postJson('/merchant/auth/logout', {}).pipe(
      tap(() => this.user.set(null)),
      map(() => undefined),
      catchError(() => {
        this.user.set(null);
        return of(undefined);
      }),
    );
  }
}
