import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { SplitAuthLayoutComponent } from '../../../shared/ui/split-auth-layout/split-auth-layout.component';
import { OtpInputComponent } from '../../../shared/ui/otp-input/otp-input.component';
import { AuthService } from '../../../core/services/auth.service';
import { OtpService } from '../../../core/services/otp.service';
import { InlineAlertComponent } from '../../../shared/ui/inline-alert/inline-alert.component';
import { NotificationService } from '../../../core/services/notification.service';
import { LocaleService } from '../../../core/services/locale.service';

@Component({
  selector: 'app-verify',
  standalone: true,
  imports: [ReactiveFormsModule, MatButtonModule, SplitAuthLayoutComponent, OtpInputComponent, InlineAlertComponent],
  template: `
    <app-split-auth-layout>
      <div class="card">
        <p class="kicker">Verification</p>
        <h2>{{ channel() === 'mobile' ? 'Verify your mobile' : 'Verify your email' }}</h2>
        <p class="sub">
          Enter the 6-digit code sent to
          <strong>{{ target() }}</strong>.
          {{ otp.channelHint(channel()) }}
          @if (otp.testModeHint(); as hint) {
            <span class="dev-hint">{{ hint }}</span>
          }
        </p>

        <form [formGroup]="form" (ngSubmit)="submit()">
          <app-otp-input formControlName="code" />
          @if (error()) {
            <app-inline-alert [message]="error()" />
          }
          <button mat-flat-button class="ps-primary-btn" type="submit" [disabled]="form.invalid || loading()">
            {{ loading() ? 'Verifying…' : 'Verify' }}
          </button>
        </form>

        <p class="resend">
          @if (seconds() > 0) {
            Resend available in {{ seconds() }}s
          } @else {
            <button type="button" class="link" (click)="resend()">Resend OTP</button>
          }
        </p>
      </div>
    </app-split-auth-layout>
  `,
  styles: [
    `
      .card {
        width: min(440px, 100%);
      }
      h2 {
        margin: 0 0 8px;
        font-size: 28px;
        letter-spacing: -0.04em;
      }
      .kicker {
        margin: 0 0 8px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #7a3dff;
      }
      .sub {
        color: #6d6484;
      }
      .dev-hint {
        display: block;
        margin-top: 8px;
        font-size: 12px;
        color: #8a819d;
      }
      form {
        display: grid;
        gap: 18px;
        margin-top: 24px;
      }
      .resend {
        margin-top: 16px;
        color: #6d6484;
      }
      .link {
        border: 0;
        background: none;
        color: #1b4dfe;
        font-weight: 650;
      }
      code {
        background: #ece8f6;
        padding: 1px 6px;
        border-radius: 6px;
      }
    `,
  ],
})
export class VerifyComponent implements OnInit, OnDestroy {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  readonly otp = inject(OtpService);
  private readonly router = inject(Router);
  private readonly notify = inject(NotificationService);
  private readonly locale = inject(LocaleService);
  private timer?: ReturnType<typeof setInterval>;

  readonly loading = signal(false);
  readonly error = signal('');
  readonly seconds = signal(30);
  readonly channel = computed<'mobile' | 'email'>(() => {
    const user = this.auth.user();
    if (this.auth.registrationPending() || !user) {
      const status = this.auth.registrationStatus();
      return status.mobileVerified ? 'email' : 'mobile';
    }
    return user && !user.mobileVerified ? 'mobile' : 'email';
  });
  readonly target = computed(() => {
    const user = this.auth.user();
    const contact = this.auth.registrationContact();
    if (this.channel() === 'mobile') {
      const mobile = user?.mobile || contact.mobile;
      return mobile ? `${this.locale.market().dialingCode} ${mobile}` : this.locale.market().dialingCode;
    }
    return user?.email || contact.email;
  });

  readonly form = this.fb.nonNullable.group({
    code: ['', [Validators.required, Validators.minLength(6), Validators.maxLength(6)]],
  });

  ngOnInit(): void {
    this.otp.loadConfig().subscribe();
    if (!this.auth.user() && !this.auth.registrationPending()) {
      this.auth.hydrate().subscribe((user) => {
        if (!user && !this.auth.registrationPending()) {
          void this.router.navigate(['/login']);
          return;
        }
        if (user?.mobileVerified && user.emailVerified) {
          void this.router.navigate(['/app/account']);
        }
      });
    } else {
      const user = this.auth.user();
      if (user?.mobileVerified && user.emailVerified) {
        void this.router.navigate(['/app/account']);
      }
    }
    this.startTimer();
  }

  ngOnDestroy(): void {
    if (this.timer) {
      clearInterval(this.timer);
    }
  }

  submit(): void {
    if (this.form.invalid) {
      return;
    }
    this.loading.set(true);
    this.error.set('');
    this.auth.verifyOtp(this.channel(), this.form.controls.code.value).subscribe({
      next: (user) => {
        this.loading.set(false);
        this.form.reset();
        if (user.mobileVerified && user.emailVerified) {
          void this.router.navigate(['/app/account']);
        } else {
          this.startTimer();
        }
      },
      error: (err: Error) => {
        this.loading.set(false);
        this.error.set(err.message);
      },
    });
  }

  resend(): void {
    const channel = this.channel();
    this.auth.resendRegistrationOtp(channel).subscribe({
      next: () => {
        this.notify.success(
          channel === 'mobile'
            ? 'A new code has been sent by SMS (Kaleyra).'
            : 'A new code has been sent to your email.',
        );
        this.startTimer();
      },
      error: (err: Error) => {
        this.error.set(err.message);
      },
    });
  }

  private startTimer(): void {
    this.seconds.set(this.otp.config().otpCooldownSeconds || 30);
    if (this.timer) {
      clearInterval(this.timer);
    }
    this.timer = setInterval(() => {
      const next = this.seconds() - 1;
      this.seconds.set(next);
      if (next <= 0 && this.timer) {
        clearInterval(this.timer);
      }
    }, 1000);
  }
}
