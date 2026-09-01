import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { OnboardingService } from '../../core/services/onboarding.service';
import { AuthService } from '../../core/services/auth.service';
import { agreementDone, kybApproved, partnerSigned } from '../../core/models/onboarding.models';

@Component({
  selector: 'app-agreement',
  standalone: true,
  imports: [
    DatePipe,
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule,
  ],
  template: `
    @if (!ready()) {
      <article class="card">
        <h3>Agreement is locked</h3>
        <p>Payswap admin must approve your KYC and KYB before you can e-sign.</p>
        <a mat-flat-button color="primary" routerLink="/app/account">Go to activation</a>
      </article>
    } @else if (fullySigned()) {
      <article class="card">
        <h3>Partner agreement complete</h3>
        <p>
          You signed as {{ app()?.agreement?.signerName }} on
          {{ app()?.agreement?.signedAt | date: 'medium' }}.
          Payswap admin {{ app()?.agreement?.adminSignerName }} countersigned on
          {{ app()?.agreement?.adminSignedAt | date: 'medium' }}.
        </p>
        <a mat-stroked-button routerLink="/app">Open dashboard</a>
      </article>
    } @else if (youSigned()) {
      <article class="card">
        <h3>Waiting for Payswap admin</h3>
        <p>
          You signed on {{ app()?.agreement?.signedAt | date: 'medium' }}.
          Admin must countersign in the admin panel to unlock live ordering.
        </p>
        <a mat-stroked-button routerLink="/app">Back to dashboard</a>
      </article>
    } @else {
      <article class="card">
        <h3>Payswap Partner Agreement</h3>
        <div class="msa">
          <p>
            Between Payswap and
            <strong>{{ app()?.profile?.legalName || 'the partner' }}</strong>
            for prepaid cards and brand vouchers.
          </p>
          <p>1. Partner may place orders for brand vouchers and prepaid card loads subject to inventory and KYC / KYB approval.</p>
          <p>2. Corporates may use products for employee, channel, and customer gifting.</p>
          <p>3. Commercial terms, SLAs, and settlement of order invoices follow the commercial schedule shared by Payswap.</p>
          <p>4. Payswap may pause live ordering if due diligence fails or documents are found inaccurate.</p>
          <p>5. This agreement is effective only after both the partner authorised signatory and Payswap admin have e-signed.</p>
        </div>
        <mat-checkbox [(ngModel)]="read">I have read the partner agreement</mat-checkbox>
        <mat-checkbox [(ngModel)]="authorised">I am authorised to e-sign for this business</mat-checkbox>
        <mat-form-field appearance="outline">
          <mat-label>Full name of signatory</mat-label>
          <input matInput [(ngModel)]="signerName" />
        </mat-form-field>
        @if (error()) {
          <p class="error">{{ error() }}</p>
        }
        <button mat-flat-button color="primary" type="button" (click)="sign()" [disabled]="busy()">
          {{ busy() ? 'Signing…' : 'eSign as partner' }}
        </button>
      </article>
    }
  `,
  styles: [
    `
      .card {
        max-width: 720px;
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 16px;
        padding: 22px;
        display: grid;
        gap: 12px;
      }
      .msa {
        max-height: 240px;
        overflow: auto;
        padding: 12px 14px;
        border-radius: 12px;
        background: #f7f4ff;
        color: #3b3550;
        font-size: 14px;
        line-height: 1.55;
      }
      .error {
        color: #b42318;
        margin: 0;
      }
    `,
  ],
})
export class AgreementComponent {
  private readonly onboarding = inject(OnboardingService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly app = this.onboarding.application;
  readonly ready = computed(() => kybApproved(this.app()));
  readonly youSigned = computed(() => partnerSigned(this.app()));
  readonly fullySigned = computed(() => agreementDone(this.app()));
  readonly busy = signal(false);
  readonly error = signal('');
  read = false;
  authorised = false;
  signerName = this.auth.user()?.fullName ?? '';

  sign(): void {
    this.error.set('');
    if (!this.read || !this.authorised || !this.signerName.trim()) {
      this.error.set('Read the agreement, confirm authority, and type the signatory name.');
      return;
    }
    this.busy.set(true);
    this.onboarding
      .signAgreement({
        read: true,
        authorised: true,
        eSigned: true,
        signerName: this.signerName.trim(),
        adminSigned: false,
        adminSignerName: '',
      })
      .subscribe({
        next: () => {
          this.busy.set(false);
          void this.router.navigate(['/app/account']);
        },
        error: (err: Error) => {
          this.busy.set(false);
          this.error.set(err.message);
        },
      });
  }
}
