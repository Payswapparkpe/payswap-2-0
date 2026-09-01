import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { SplitAuthLayoutComponent } from '../../../shared/ui/split-auth-layout/split-auth-layout.component';
import { OtpInputComponent } from '../../../shared/ui/otp-input/otp-input.component';
import { AuthService } from '../../../core/services/auth.service';
import { passwordStrength } from '../../../core/validators/india.validators';
import { InlineAlertComponent } from '../../../shared/ui/inline-alert/inline-alert.component';
import { NotificationService } from '../../../core/services/notification.service';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    SplitAuthLayoutComponent,
    OtpInputComponent,
    InlineAlertComponent,
  ],
  template: `
    <app-split-auth-layout>
      <div class="card">
        <p class="kicker">Reset access</p>
        <h2>Forgot password</h2>
        <p class="sub">We’ll send a demo OTP to the email or mobile on the account.</p>

        <form [formGroup]="form" (ngSubmit)="submit()">
          <mat-form-field appearance="outline">
            <mat-label>Email or mobile</mat-label>
            <input matInput formControlName="identifier" />
          </mat-form-field>
          <p class="label">OTP</p>
          <app-otp-input formControlName="code" aria-describedby="otp-help" />
          <p id="otp-help" class="assistive">Enter the 6-digit code sent to your registered channel.</p>
          <mat-form-field appearance="outline">
            <mat-label>New password</mat-label>
            <input matInput type="password" formControlName="password" />
          </mat-form-field>
          @if (error()) {
            <app-inline-alert [message]="error()" />
          }
          @if (done()) {
            <app-inline-alert tone="success" message="Password updated. You can sign in now." />
          }
          <button mat-flat-button class="ps-primary-btn" type="submit" [disabled]="form.invalid || loading()">
            {{ loading() ? 'Updating…' : 'Reset password' }}
          </button>
        </form>
        <p class="switch"><a routerLink="/login">Back to sign in</a></p>
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
      .switch,
      .label {
        color: #6d6484;
      }
      form {
        display: grid;
        gap: 10px;
        margin-top: 20px;
      }
      .assistive {
        margin: -4px 0 4px;
        color: #8a819d;
        font-size: 12px;
      }
    `,
  ],
})
export class ForgotPasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly notify = inject(NotificationService);

  readonly loading = signal(false);
  readonly error = signal('');
  readonly done = signal(false);

  readonly form = this.fb.nonNullable.group({
    identifier: ['', Validators.required],
    code: ['', [Validators.required, Validators.minLength(6)]],
    password: ['', [Validators.required, passwordStrength()]],
  });

  submit(): void {
    if (this.form.invalid) {
      return;
    }
    this.loading.set(true);
    this.error.set('');
    const { identifier, code, password } = this.form.getRawValue();
    this.auth.resetPassword(identifier, code, password).subscribe({
      next: () => {
        this.loading.set(false);
        this.done.set(true);
        this.notify.success('Password updated successfully.');
        setTimeout(() => void this.router.navigate(['/login']), 900);
      },
      error: (err: Error) => {
        this.loading.set(false);
        this.error.set(err.message);
        this.notify.error(err.message);
      },
    });
  }
}
