import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { OnboardingService } from '../../core/services/onboarding.service';
import { AuthService } from '../../core/services/auth.service';
import {
  agreementDone,
  ENTITY_LABELS,
  isLive,
  kybApproved,
  kycDone,
  partnerSigned,
} from '../../core/models/onboarding.models';

@Component({
  selector: 'app-account-hub',
  standalone: true,
  imports: [RouterLink, MatButtonModule],
  template: `
    @if (app(); as application) {
      @if (application.returnReason && application.status === 'draft') {
        <p class="alert warn">Admin asked for corrections: {{ application.returnReason }}</p>
      }
      @if (application.status === 'under_review') {
        <p class="alert info">Your file is under admin review. Details are locked until approval or a resubmit request.</p>
      }
      <p class="lede">
        Activation is separate from ordering. Verify your identity first, then complete entity KYB
        for admin review, e-sign the partner agreement, then wait for Payswap admin to countersign.
      </p>
      <div class="cards">
        <article>
          <p class="kicker">01</p>
          <h3>KYC</h3>
          <p>Your identity as an individual.</p>
          <strong [class.done]="kyc()">{{ kyc() ? 'Verified' : 'Pending' }}</strong>
          <a mat-stroked-button routerLink="/app/onboarding">{{ kyc() ? 'Review KYC' : 'Complete KYC' }}</a>
        </article>
        <article [class.locked]="!kyc()">
          <p class="kicker">02</p>
          <h3>KYB</h3>
          <p>Entity type, business docs, bank, and admin verification.</p>
          <strong [class.done]="kyb()" [class.review]="application.status === 'under_review'">
            {{ kybLabel() }}
          </strong>
          @if (kyc()) {
            <a mat-stroked-button routerLink="/app/onboarding">{{ kyb() ? 'View KYB file' : 'Complete KYB' }}</a>
          } @else {
            <button mat-stroked-button disabled>After KYC verification</button>
          }
        </article>
        <article [class.locked]="!kyb()">
          <p class="kicker">03</p>
          <h3>Agreement</h3>
          <p>You e-sign; Payswap admin countersigns.</p>
          <strong [class.done]="signed()">{{ agreementLabel() }}</strong>
          @if (kyb()) {
            <a mat-flat-button color="primary" routerLink="/app/agreement">
              {{ partnerSignedOnly() || signed() ? 'View agreement' : 'Sign agreement' }}
            </a>
          } @else {
            <button mat-stroked-button disabled>After KYB approval</button>
          }
        </article>
      </div>
      <dl>
        <div><dt>User ID</dt><dd>{{ auth.user()?.publicId || application.userId || '—' }}</dd></div>
        @if (application.merchantId) {
          <div><dt>Merchant ID</dt><dd>{{ application.merchantId }}</dd></div>
        }
        <div><dt>Legal name</dt><dd>{{ application.profile.legalName || '—' }}</dd></div>
        <div>
          <dt>Entity</dt>
          <dd>{{ application.profile.entityType ? labels[application.profile.entityType] : '—' }}</dd>
        </div>
        <div><dt>PAN</dt><dd>{{ application.identity.pan || application.signatory.pan || '—' }}</dd></div>
        <div>
          <dt>Signatory / owner</dt>
          <dd>
            {{
              application.signatoryIsOwner === false
                ? 'Authorised signatory and business owner are different people.'
                : application.signatoryIsOwner
                  ? 'Authorised signatory is also a director / owner.'
                  : '—'
            }}
          </dd>
        </div>
        <div><dt>Ordering</dt><dd>{{ live() ? 'Live' : 'Test catalog' }}</dd></div>
      </dl>
    }
  `,
  styles: [
    `
      .lede {
        max-width: 720px;
        color: #6d6484;
        margin: 0 0 18px;
      }
      .alert {
        margin: 0 0 14px;
        padding: 12px 14px;
        border-radius: 12px;
        font-size: 13px;
        line-height: 1.5;
      }
      .alert.warn {
        background: #fff4e8;
        color: #9a4b00;
      }
      .alert.info {
        background: #e8f0fa;
        color: #164e8a;
      }
      .cards {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
      }
      article,
      dl {
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 16px;
        padding: 18px;
      }
      .kicker {
        margin: 0;
        font-size: 11px;
        letter-spacing: 0.14em;
        color: #8a819d;
        font-weight: 700;
      }
      h3 {
        margin: 6px 0 8px;
      }
      article p {
        color: #6d6484;
        min-height: 44px;
      }
      strong {
        display: block;
        margin: 0 0 14px;
        color: #9a4b00;
      }
      .done {
        color: #0f7a3d;
      }
      .review {
        color: #1b4dfe;
      }
      .locked {
        opacity: 0.78;
      }
      dl {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
        margin-top: 16px;
      }
      dt {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #8a819d;
      }
      dd {
        margin: 4px 0 0;
        font-weight: 650;
      }
      @media (max-width: 900px) {
        .cards,
        dl {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class AccountHubComponent {
  private readonly onboarding = inject(OnboardingService);
  readonly auth = inject(AuthService);
  readonly app = this.onboarding.application;
  readonly labels = ENTITY_LABELS;
  readonly kyc = computed(() => kycDone(this.app()));
  readonly kyb = computed(() => kybApproved(this.app()));
  readonly partnerSignedOnly = computed(() => partnerSigned(this.app()));
  readonly signed = computed(() => agreementDone(this.app()));
  readonly live = computed(() => isLive(this.app()));

  kybLabel(): string {
    const app = this.app();
    if (this.kyb()) {
      return 'Approved by admin';
    }
    if (app?.status === 'under_review') {
      return 'With Payswap admin';
    }
    if (!this.kyc()) {
      return 'Locked until KYC';
    }
    return 'In progress';
  }

  agreementLabel(): string {
    if (this.signed()) {
      return 'Dual-signed';
    }
    if (this.partnerSignedOnly()) {
      return 'Awaiting admin countersign';
    }
    if (this.kyb()) {
      return 'Ready for your e-sign';
    }
    return 'Locked until KYB approval';
  }
}
