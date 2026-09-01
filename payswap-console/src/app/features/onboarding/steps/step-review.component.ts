import { DatePipe } from '@angular/common';
import { Component, EventEmitter, Input, Output, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { RouterLink } from '@angular/router';
import { ENTITY_LABELS, KycApplication } from '../../../core/models/onboarding.models';
import { OnboardingService } from '../../../core/services/onboarding.service';
import { prevOnboardingStep, resolvedSignatoryIsOwner, rulesFor } from '../../../core/config/entity-rules';

@Component({
  selector: 'app-step-review',
  standalone: true,
  imports: [DatePipe, FormsModule, RouterLink, MatButtonModule, MatCheckboxModule],
  template: `
    <div class="summary">
      <section>
        <h4>Name match</h4>
        <ul>
          <li>Legal / PAN name: <strong>{{ application.profile.legalName || '—' }}</strong></li>
          <li>GSTIN: <strong>{{ hideGst ? 'Not applicable' : application.profile.noGstin ? 'Not enrolled' : application.profile.gstin || '—' }}</strong></li>
          <li>Bank holder: <strong>{{ application.bank.holderName || '—' }}</strong></li>
        </ul>
        @if (!namesAlign) {
          <p class="warn">Names differ. Compliance will likely query this — fix before submit if you can.</p>
        }
      </section>
      <section>
        <h4>Entity</h4>
        <p>
          {{ application.profile.brandName }} ·
          {{ application.profile.entityType ? labels[application.profile.entityType] : '—' }}
        </p>
        <p>
          Signatory {{ application.signatory.verified ? 'verified' : 'pending' }} via
          {{ application.signatory.path === 'digilocker' ? 'DigiLocker' : application.signatory.path || '—' }}
        </p>
        <p>
          {{
            application.kycPersonIsAuthorisedSignatory === false
              ? 'KYC person is not the authorised signatory (' + (application.authorisedSignatoryName || 'name pending') + ').'
              : 'KYC person is the authorised signatory.'
          }}
          Relation: {{ application.signatoryRelation || '—' }}.
        </p>
        <p>
          {{
            resolvedSignatoryIsOwner(application)
              ? 'Authorised signatory is also a director / owner. A board resolution appointing that signatory is still required for companies and LLPs.'
              : 'Authorised signatory is not an owner — owner person KYC is on file, plus a board resolution appointing the signatory.'
          }}
        </p>
        @if (application.signatoryIsOwner === false) {
          <p>
            Owner KYC:
            <strong>{{ application.ownerKyc.verified ? application.ownerKyc.name || 'Verified' : 'Pending' }}</strong>
          </p>
        }
        @if (application.ubos.length) {
          <p>{{ application.ubos.length }} owner{{ application.ubos.length === 1 ? '' : 's' }} listed.</p>
        }
      </section>
    </div>

    <h4>Declarations</h4>
    <div class="checks">
      <mat-checkbox [(ngModel)]="application.compliance.authorisedDeclaration" [disabled]="readonly">
        I am authorised to onboard this business with Payswap
      </mat-checkbox>
      <mat-checkbox [(ngModel)]="application.compliance.truthDeclaration" [disabled]="readonly">
        Information and documents provided are true and complete
      </mat-checkbox>
      <mat-checkbox [(ngModel)]="application.compliance.dpdpConsent" [disabled]="readonly">
        DPDP consent for processing KYC / KYB data
      </mat-checkbox>
    </div>

        @if (application.status === 'draft' && application.returnReason) {
          <p class="warn">Admin returned this file: {{ application.returnReason }}</p>
        }
    @if (error()) {
      <p class="error">{{ error() }}</p>
    }

    <div class="actions">
      <button mat-button type="button" (click)="back()">Back</button>
      @if (application.status !== 'under_review' && application.status !== 'pending_agreement' && application.status !== 'pending_admin_sign' && application.status !== 'activated') {
        <button mat-flat-button color="primary" type="button" (click)="submit()" [disabled]="submitting()">
          {{ submitting() ? 'Submitting…' : 'Submit KYC / KYB for admin review' }}
        </button>
      }
    </div>

    @if (application.status === 'under_review') {
      <div class="ticket">
        <h4>With Payswap admin</h4>
        <p>Submitted {{ application.submittedAt | date: 'medium' }}. KYC and KYB are approved by Payswap admin only. You can e-sign after approval.</p>
      </div>
    }
    @if (application.status === 'pending_agreement') {
      <div class="ticket">
        <h4>KYC and KYB approved</h4>
        <p>Next: e-sign the partner agreement. Admin will countersign after you.</p>
        <a mat-flat-button color="primary" routerLink="/app/agreement">Go to agreement</a>
      </div>
    }
    @if (application.status === 'pending_admin_sign') {
      <div class="ticket">
        <h4>Waiting for admin countersign</h4>
        <p>You have signed. Ask Payswap admin (admin&#64;payswap.in) to countersign in Admin → Partners.</p>
      </div>
    }
    @if (application.status === 'activated') {
      <p class="ok">Live partner since {{ application.activatedAt | date: 'medium' }}. Dual agreement is on file.</p>
    }
  `,
  styles: [
    `
      .summary {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
      }
      section,
      .ticket {
        background: #f7f4ff;
        padding: 14px;
        border-radius: 14px;
      }
      .checks {
        display: grid;
        gap: 8px;
        margin: 8px 0 16px;
      }
      .warn {
        color: #9a4b00;
      }
      .error {
        color: #b42318;
      }
      .ok {
        color: #0f7a3d;
        font-weight: 650;
      }
      .muted-note {
        color: #8a819d;
        font-size: 12px;
        margin: 8px 0 0;
      }
      .actions {
        display: flex;
        justify-content: space-between;
        margin: 12px 0;
      }
      @media (max-width: 720px) {
        .summary {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class StepReviewComponent {
  private readonly onboarding = inject(OnboardingService);
  @Input({ required: true }) application!: KycApplication;
  @Input() readonly = false;
  @Output() save = new EventEmitter<KycApplication>();

  readonly labels = ENTITY_LABELS;
  readonly resolvedSignatoryIsOwner = resolvedSignatoryIsOwner;

  get hideGst(): boolean {
    return rulesFor(this.application.profile.entityType)?.gst === 'hidden';
  }
  readonly submitting = signal(false);
  readonly error = signal('');

  get namesAlign(): boolean {
    const rules = rulesFor(this.application.profile.entityType);
    const expected =
      rules?.bankMatches === 'person'
        ? this.application.signatory.name
        : this.application.profile.legalName;
    const legal = expected.trim().toLowerCase();
    const bank = this.application.bank.holderName.trim().toLowerCase();
    return !legal || !bank || legal === bank;
  }

  back(): void {
    this.save.emit({
      ...this.application,
      currentStep: prevOnboardingStep('review', this.application.profile.entityType, this.application.signatoryIsOwner),
    });
  }

  submit(): void {
    const c = this.application.compliance;
    if (!c.authorisedDeclaration || !c.truthDeclaration || !c.dpdpConsent) {
      this.error.set('Accept the declarations to submit.');
      return;
    }
    this.submitting.set(true);
    this.onboarding.save(this.application).subscribe(() => {
      this.onboarding.submit().subscribe({
        next: () => this.submitting.set(false),
        error: (err: Error) => {
          this.submitting.set(false);
          this.error.set(err.message);
        },
      });
    });
  }
}
