import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { SplitAuthLayoutComponent } from '../../../shared/ui/split-auth-layout/split-auth-layout.component';
import { InlineAlertComponent } from '../../../shared/ui/inline-alert/inline-alert.component';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-reset-password',
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
        @if (invalid()) {
          <h2>Link expired</h2>
          <p class="sub">This reset link is invalid or has already been used.</p>
          <app-inline-alert tone="error" message="Request a fresh reset link and try again." />
          <p class="switch"><a routerLink="/forgot-password">Request new link</a></p>
        } @else if (done()) {
          <h2>Password updated</h2>
          <p class="sub">Your password was changed and all sessions were signed out.</p>
          <app-inline-alert tone="success" message="You can now sign in with your new password." />
          <p class="switch"><a routerLink="/login">Back to sign in</a></p>
        } @else {
          <h2>Choose a new password</h2>
          <p class="sub">Pick a strong password you have not used on Payswap before.</p>
          <form [formGroup]="form" (ngSubmit)="submit()">
            <mat-form-field appearance="outline">
              <mat-label>New password</mat-label>
              <input matInput type="password" formControlName="password" autocomplete="new-password" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Confirm password</mat-label>
              <input matInput type="password" formControlName="confirmPassword" autocomplete="new-password" />
            </mat-form-field>
            @if (error()) {
              <app-inline-alert [message]="error()" />
            }
            <button mat-flat-button class="ps-primary-btn" type="submit" [disabled]="form.invalid || loading()">
              {{ loading() ? 'Updating…' : 'Update password' }}
            </button>
          </form>
        }
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
export class ResetPasswordComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);

  readonly loading = signal(false);
  readonly error = signal('');
  readonly done = signal(false);
  readonly invalid = signal(false);

  private uid = '';
  private token = '';

  readonly form = this.fb.nonNullable.group({
    password: ['', [Validators.required, Validators.minLength(8)]],
    confirmPassword: ['', Validators.required],
  });

  ngOnInit(): void {
    this.uid = this.route.snapshot.paramMap.get('uid') || '';
    this.token = this.route.snapshot.paramMap.get('token') || '';
    if (!this.uid || !this.token) {
      this.invalid.set(true);
      return;
    }
    this.auth.validatePasswordResetLink(this.uid, this.token).subscribe({
      error: () => this.invalid.set(true),
    });
  }

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { password, confirmPassword } = this.form.getRawValue();
    if (password !== confirmPassword) {
      this.error.set('The passwords do not match.');
      return;
    }
    this.loading.set(true);
    this.error.set('');
    this.auth.confirmPasswordReset(this.uid, this.token, password, confirmPassword).subscribe({
      next: () => {
        this.loading.set(false);
        this.done.set(true);
      },
      error: (err: Error) => {
        this.loading.set(false);
        this.error.set(err.message || 'Could not update password.');
      },
    });
  }
}
