import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { SplitAuthLayoutComponent } from '../../../shared/ui/split-auth-layout/split-auth-layout.component';
import { AuthService } from '../../../core/services/auth.service';
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
    InlineAlertComponent,
  ],
  template: `
    <app-split-auth-layout>
      <div class="card">
        <p class="kicker">Reset access</p>
        <h2>Forgot password</h2>
        <p class="sub">
          Enter the email on your account. If it exists, we will send a secure reset link. Mobile OTP
          (Kaleyra) is used for sign-up and verification, not password reset.
        </p>

        <form [formGroup]="form" (ngSubmit)="submit()">
          <mat-form-field appearance="outline">
            <mat-label>Work email</mat-label>
            <input matInput type="email" formControlName="identifier" autocomplete="email" />
          </mat-form-field>
          @if (error()) {
            <app-inline-alert [message]="error()" />
          }
          @if (done()) {
            <app-inline-alert
              tone="success"
              message="If that email is registered, a reset link is on its way. Check your inbox."
            />
          }
          <button mat-flat-button class="ps-primary-btn" type="submit" [disabled]="form.invalid || loading()">
            {{ loading() ? 'Sending…' : 'Send reset link' }}
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
      .switch {
        color: #6d6484;
      }
      form {
        display: grid;
        gap: 10px;
        margin-top: 20px;
      }
    `,
  ],
})
export class ForgotPasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);

  readonly loading = signal(false);
  readonly error = signal('');
  readonly done = signal(false);

  readonly form = this.fb.nonNullable.group({
    identifier: ['', [Validators.required, Validators.email]],
  });

  submit(): void {
    if (this.form.invalid) {
      return;
    }
    this.loading.set(true);
    this.error.set('');
    const { identifier } = this.form.getRawValue();
    this.auth.resetPassword(identifier).subscribe({
      next: () => {
        this.loading.set(false);
        this.done.set(true);
        this.notify.success('Check your email for the reset link.');
      },
      error: (err: Error) => {
        this.loading.set(false);
        this.error.set(err.message);
      },
    });
  }
}
