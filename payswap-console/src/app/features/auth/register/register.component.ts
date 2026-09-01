import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { SplitAuthLayoutComponent } from '../../../shared/ui/split-auth-layout/split-auth-layout.component';
import { AuthService } from '../../../core/services/auth.service';
import { indianMobile, passwordScore, passwordStrength } from '../../../core/validators/india.validators';
import { InlineAlertComponent } from '../../../shared/ui/inline-alert/inline-alert.component';
import { NotificationService } from '../../../core/services/notification.service';
import { DEFAULT_MARKET } from '../../../core/config/market.config';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule,
    SplitAuthLayoutComponent,
    InlineAlertComponent,
  ],
  template: `
    <app-split-auth-layout>
      <div class="card">
        <p class="kicker">Partner signup</p>
        <h2>Create your corporate account</h2>
        <p class="sub">Order employee gifts, brand vouchers, and prepaid cards after KYC and KYB.</p>

        <form [formGroup]="form" (ngSubmit)="submit()">
          <mat-form-field appearance="outline">
            <mat-label>Full name</mat-label>
            <input matInput formControlName="fullName" autocomplete="name" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Work email</mat-label>
            <input matInput type="email" formControlName="email" autocomplete="email" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Mobile number</mat-label>
            <input matInput formControlName="mobile" inputmode="numeric" maxlength="10" autocomplete="tel" />
            @if (form.controls.mobile.touched && form.controls.mobile.hasError('mobile')) {
              <mat-error>Enter a valid {{ mobileHelp }}.</mat-error>
            }
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Password</mat-label>
            <input matInput type="password" formControlName="password" autocomplete="new-password" />
            @if (form.controls.password.touched && form.controls.password.hasError('passwordStrength')) {
              <mat-error>Use 8+ chars with upper, lower, number, and symbol.</mat-error>
            }
          </mat-form-field>

          <div class="strength" aria-hidden="true">
            @for (n of [1, 2, 3, 4, 5]; track n) {
              <span [class.on]="score() >= n"></span>
            }
          </div>
          <p class="assistive" aria-live="polite">Password strength: {{ score() }}/5</p>

          <mat-checkbox formControlName="terms">I agree to the Terms of Service</mat-checkbox>
          <mat-checkbox formControlName="dpdp">
            I consent to processing of my personal data under the DPDP Act for onboarding
          </mat-checkbox>

          @if (error()) {
            <app-inline-alert [message]="error()" />
          }

          <button mat-flat-button class="ps-primary-btn" type="submit" [disabled]="form.invalid || loading()">
            {{ loading() ? 'Creating account…' : 'Continue to verification' }}
          </button>
        </form>

        <p class="switch">Already registered? <a routerLink="/login">Sign in</a></p>
      </div>
    </app-split-auth-layout>
  `,
  styles: [
    `
      .card {
        width: min(440px, 100%);
      }
      h2 {
        margin: 0 0 6px;
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
      .sub,
      .switch {
        color: #6d6484;
      }
      form {
        display: grid;
        margin-top: 18px;
        gap: 2px;
      }
      .strength {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 6px;
        margin: 0 0 12px;
      }
      .strength span {
        height: 4px;
        border-radius: 99px;
        background: #ddd6ea;
      }
      .strength span.on {
        background: linear-gradient(90deg, #1b4dfe, #ac24ff);
      }
      .assistive {
        margin: -6px 0 8px;
        color: #8a819d;
        font-size: 12px;
      }
    `,
  ],
})
export class RegisterComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly notify = inject(NotificationService);

  readonly loading = signal(false);
  readonly error = signal('');
  readonly score = signal(0);
  readonly mobileHelp = DEFAULT_MARKET.mobileLabel;

  readonly form = this.fb.nonNullable.group({
    fullName: ['', [Validators.required, Validators.minLength(2)]],
    email: ['', [Validators.required, Validators.email]],
    mobile: ['', [Validators.required, indianMobile()]],
    password: ['', [Validators.required, passwordStrength()]],
    terms: [false, Validators.requiredTrue],
    dpdp: [false, Validators.requiredTrue],
  });

  constructor() {
    this.form.controls.password.valueChanges.subscribe((value) => {
      this.score.set(passwordScore(value));
    });
  }

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.error.set('');
    const { fullName, email, mobile, password } = this.form.getRawValue();
    this.auth.register({ fullName, email, mobile, password, partnerType: 'corporate' }).subscribe({
      next: () => {
        this.loading.set(false);
        void this.router.navigate(['/verify']);
      },
      error: (err: Error) => {
        this.loading.set(false);
        this.error.set(err.message);
        this.notify.error(err.message);
      },
    });
  }
}
