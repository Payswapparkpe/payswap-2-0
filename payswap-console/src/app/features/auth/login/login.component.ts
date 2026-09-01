import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { SplitAuthLayoutComponent } from '../../../shared/ui/split-auth-layout/split-auth-layout.component';
import { AuthService } from '../../../core/services/auth.service';
import { InlineAlertComponent } from '../../../shared/ui/inline-alert/inline-alert.component';
import { NotificationService } from '../../../core/services/notification.service';
import { TPipe } from '../../../shared/pipes/t.pipe';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule,
    SplitAuthLayoutComponent,
    InlineAlertComponent,
    TPipe,
  ],
  template: `
    <app-split-auth-layout>
      <div class="card">
        <p class="kicker">Welcome back</p>
        <h2>{{ 'signIn' | t }} to Payswap</h2>
        <p class="sub">Corporate partners sign in here. Payswap staff and admins use the Django staff portal.</p>

        <form [formGroup]="form" (ngSubmit)="submit()">
          <mat-form-field appearance="outline">
            <mat-label>Email or mobile</mat-label>
            <input matInput formControlName="identifier" autocomplete="username" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Password</mat-label>
            <input
              matInput
              [type]="hide() ? 'password' : 'text'"
              formControlName="password"
              autocomplete="current-password"
            />
            <button
              mat-icon-button
              matSuffix
              type="button"
              (click)="hide.set(!hide())"
              [attr.aria-label]="hide() ? 'Show password' : 'Hide password'"
            >
              <mat-icon>{{ hide() ? 'visibility' : 'visibility_off' }}</mat-icon>
            </button>
          </mat-form-field>

          <a class="forgot" routerLink="/forgot-password">Forgot password?</a>

          @if (error()) {
            <app-inline-alert [message]="error()" />
          }

          <button mat-flat-button class="ps-primary-btn" type="submit" [disabled]="form.invalid || loading()">
            {{ loading() ? 'Signing in…' : ('signIn' | t) }}
          </button>
        </form>

        <p class="switch">
          New partner?
          <a routerLink="/register">Create an account</a>
        </p>
        <p class="hint">
          Demo corporate: <code>merchant&#64;payswap.local</code> · password <code>CorrectHorse9!</code>
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
      .switch,
      .hint {
        color: #6d6484;
      }
      form {
        display: grid;
        margin-top: 22px;
      }
      .forgot {
        justify-self: end;
        margin: -6px 0 14px;
        font-size: 13px;
        font-weight: 650;
        color: #1b4dfe;
      }
      .switch {
        margin-top: 22px;
      }
      .hint {
        font-size: 12px;
      }
      code {
        background: #ece8f6;
        padding: 1px 6px;
        border-radius: 6px;
      }
    `,
  ],
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly notify = inject(NotificationService);

  readonly hide = signal(true);
  readonly loading = signal(false);
  readonly error = signal('');

  readonly form = this.fb.nonNullable.group({
    identifier: ['', Validators.required],
    password: ['', Validators.required],
  });

  submit(): void {
    if (this.form.invalid) {
      return;
    }
    this.loading.set(true);
    this.error.set('');
    const { identifier, password } = this.form.getRawValue();
    this.auth.login(identifier, password).subscribe({
      next: (user) => {
        this.loading.set(false);
        if (!user.mobileVerified || !user.emailVerified) {
          void this.router.navigate(['/verify']);
          return;
        }
        void this.router.navigate(['/app']);
      },
      error: (err: Error & { useStaffPortal?: boolean; staffLoginUrl?: string }) => {
        this.loading.set(false);
        if (err.useStaffPortal && err.staffLoginUrl) {
          window.location.href = err.staffLoginUrl;
          return;
        }
        this.error.set(err.message);
        this.notify.error(err.message);
      },
    });
  }
}
