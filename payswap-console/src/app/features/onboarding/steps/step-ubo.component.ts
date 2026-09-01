import { Component, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { DigilockerSnapshot, KycApplication, Ubo } from '../../../core/models/onboarding.models';
import { nextOnboardingStep, prevOnboardingStep, resolvedSignatoryIsOwner, rulesFor, uboThreshold } from '../../../core/config/entity-rules';
import { VerificationService } from '../../../core/services/verification.service';
import { DigilockerSessionService } from '../../../core/services/digilocker-session.service';
import { isVerificationLocked } from '../../../core/utils/verification-lock.util';
import { MOBILE_PATTERN, PAN_PATTERN } from '../../../core/validators/india.validators';

interface UboRow extends Ubo {
  mobile?: string;
  digiConsent?: boolean;
  digilocker?: DigilockerSnapshot | null;
}

@Component({
  selector: 'app-step-ubo',
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule],
  template: `
    <div>
      @if (application.profile.entityType === 'public_limited') {
        <p>Public listed companies may skip UBO identification with a declaration.</p>
        <mat-checkbox [(ngModel)]="skipListed" [disabled]="readonly">This entity is listed; skip UBO capture</mat-checkbox>
      } @else if (!signatoryIsOwner) {
        <p>
          Authorised-signatory KYC and business-owner KYC are already on file. MCA directors from CIN
          verification are listed below. Verify KYC for at least {{ minDirectorKyc() }} director(s), plus
          any individual with more than {{ threshold }}% ownership or control.
        </p>
      } @else {
        <p>
          Directors verified on the KYB step are listed below. Confirm the list and add any other
          individual with more than {{ threshold }}% ownership or control if applicable.
        </p>
      }

      @if (!skipListed) {
        <div class="list">
          @for (ubo of ubos; track ubo.id; let i = $index) {
            <article [class.frozen]="frozen">
              <mat-form-field appearance="outline">
                <mat-label>Name</mat-label>
                <input matInput [(ngModel)]="ubo.name" [disabled]="frozen || readonly" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>PAN</mat-label>
                <input matInput [(ngModel)]="ubo.pan" [disabled]="frozen || readonly || ubo.kycVerified" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Ownership %</mat-label>
                <input matInput type="number" [(ngModel)]="ubo.ownershipPercent" [disabled]="frozen || readonly" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Relationship</mat-label>
                <input matInput [(ngModel)]="ubo.relationship" [disabled]="frozen || readonly" />
              </mat-form-field>
              @if (ubo.kycVerified && uboKycLocked(ubo)) {
                <p class="ok">KYC verified via DigiLocker.</p>
              } @else if (!readonly && !frozen) {
                <mat-form-field appearance="outline">
                  <mat-label>Mobile (DigiLocker)</mat-label>
                  <input matInput [(ngModel)]="ubo.mobile" maxlength="10" />
                </mat-form-field>
                <mat-checkbox [(ngModel)]="ubo.digiConsent">
                  Consent to fetch Aadhaar / PAN from DigiLocker
                </mat-checkbox>
                <button
                  mat-stroked-button
                  type="button"
                  (click)="verify(ubo)"
                  [disabled]="verifyBusy() === ubo.id"
                >
                  {{ verifyBusy() === ubo.id ? lockerLabel() : 'Verify director KYC' }}
                </button>
              }
              @if (ubo.digilocker?.documents?.length) {
                @for (doc of ubo.digilocker!.documents; track doc.type) {
                  <p class="fetched">{{ doc.type }} · {{ doc.name }} · {{ doc.idMasked }}</p>
                }
              }
              @if (!frozen && !readonly) {
                <button mat-button type="button" color="warn" (click)="remove(i)">Remove</button>
              }
            </article>
          }
        </div>
        @if (!frozen && !readonly) {
          <button mat-stroked-button type="button" (click)="add()">Add owner / beneficial owner</button>
        }
        <div class="freeze">
          @if (!frozen && !readonly) {
            <button mat-stroked-button type="button" (click)="frozen = true">Confirm beneficial owners</button>
          } @else if (frozen) {
            <p class="ok">List is frozen. Unlock only to correct errors.</p>
            @if (!readonly) {
              <button mat-button type="button" (click)="frozen = false">Unlock for correction</button>
            }
          }
        </div>
      }
      @if (error()) {
        <p class="error">{{ error() }}</p>
      }
      <div class="actions">
        <button mat-button type="button" (click)="back()">Back</button>
        <button mat-flat-button color="primary" type="button" (click)="next()">Save and continue</button>
      </div>
    </div>
  `,
  styles: [
    `
      .list {
        display: grid;
        gap: 12px;
        margin: 12px 0;
      }
      article {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px 12px;
        padding: 12px;
        border: 1px solid #e7e1f2;
        border-radius: 14px;
      }
      .fetched {
        grid-column: 1 / -1;
        margin: 0;
        font-size: 13px;
        color: #3d3554;
      }
      .ok {
        color: #0f7a3d;
      }
      .error {
        color: #b42318;
      }
      .actions {
        display: flex;
        justify-content: space-between;
        margin-top: 16px;
      }
      @media (max-width: 720px) {
        article {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class StepUboComponent implements OnInit {
  private readonly verification = inject(VerificationService);
  private readonly digilockerSession = inject(DigilockerSessionService);

  @Input({ required: true }) application!: KycApplication;
  @Input() readonly = false;
  @Output() save = new EventEmitter<KycApplication>();

  ubos: UboRow[] = [];
  frozen = false;
  skipListed = false;
  readonly error = signal('');
  readonly verifyBusy = signal('');
  readonly lockerLabel = signal('Connecting…');

  get threshold(): number {
    return uboThreshold(this.application.profile.entityType);
  }

  get signatoryIsOwner(): boolean {
    return resolvedSignatoryIsOwner(this.application);
  }

  minDirectorKyc(): number {
    return rulesFor(this.application.profile.entityType)?.needsCin ? 2 : 1;
  }

  uboKycLocked(ubo: UboRow): boolean {
    return isVerificationLocked(!!ubo.kycVerified, this.application, 'ubo');
  }

  ngOnInit(): void {
    this.ubos = this.application.ubos.map((u) => ({ ...u }));
    this.frozen = this.application.ubosFrozen;
    this.skipListed = this.application.publicListedSkip;
    this.seedFromRegistryDirectors();
    if (!this.ubos.length && this.signatoryIsOwner && this.application.signatory.verified) {
      this.ubos.push({
        id: crypto.randomUUID(),
        name: this.application.signatory.name,
        pan: this.application.signatory.pan,
        ownershipPercent: this.threshold + 1,
        relationship: 'Director / partner',
        kycPath: this.application.signatory.path,
        kycVerified: true,
      });
    }
  }

  add(): void {
    this.ubos.push({
      id: crypto.randomUUID(),
      name: '',
      pan: '',
      ownershipPercent: this.threshold + 1,
      relationship: 'Shareholder',
      kycVerified: false,
      mobile: '',
      digiConsent: false,
    });
  }

  remove(index: number): void {
    this.ubos.splice(index, 1);
  }

  verify(ubo: UboRow): void {
    const pan = (ubo.pan || '').trim().toUpperCase();
    const mobile = (ubo.mobile || '').trim();
    if (!ubo.name?.trim()) {
      this.error.set('Enter the director name before KYC verification.');
      return;
    }
    if (!PAN_PATTERN.test(pan)) {
      this.error.set('Enter a valid PAN for this director.');
      return;
    }
    ubo.pan = pan;
    if (!MOBILE_PATTERN.test(mobile)) {
      this.error.set('Enter the mobile number linked to DigiLocker.');
      return;
    }
    if (!ubo.digiConsent) {
      this.error.set('DigiLocker consent is required.');
      return;
    }
    this.error.set('');
    this.verifyBusy.set(ubo.id);
    this.lockerLabel.set('Opening DigiLocker…');
    this.digilockerSession.run({ mobile, pan, name: ubo.name }).subscribe({
      next: (status) => {
        this.verifyBusy.set('');
        ubo.digilocker = status;
        if (status.status !== 'AUTHENTICATED') {
          this.error.set('DigiLocker verification did not complete.');
          return;
        }
        const idDoc =
          status.documents.find((d) => d.type === 'PAN') ?? status.documents.find((d) => d.type === 'AADHAAR');
        const verifiedName = status.userDetails?.name || idDoc?.name;
        if (verifiedName) {
          ubo.name = verifiedName;
        }
        ubo.kycVerified = true;
        ubo.kycPath = 'digilocker';
      },
      error: (err: Error) => {
        this.verifyBusy.set('');
        this.error.set(err.message || 'DigiLocker verification failed.');
      },
    });
  }

  back(): void {
    this.save.emit({
      ...this.payload(),
      currentStep: prevOnboardingStep('ubo', this.application.profile.entityType, this.application.signatoryIsOwner),
    });
  }

  next(): void {
    this.error.set('');
    if (!this.skipListed) {
      if (!this.ubos.length) {
        this.error.set('Add at least one beneficial owner, or skip if the company is listed.');
        return;
      }
      const verifiedCount = this.ubos.filter((u) => u.kycVerified).length;
      const minRequired = this.minDirectorKyc();
      if (verifiedCount < minRequired) {
        this.error.set(`Verify KYC for at least ${minRequired} director(s) on the KYB step, or here.`);
        return;
      }
      if (this.ubos.some((u) => !u.name || !u.pan)) {
        this.error.set('Every owner needs name and PAN.');
        return;
      }
      if (this.ubos.some((u) => !u.kycVerified)) {
        this.error.set('Every listed owner needs KYC verification.');
        return;
      }
      const signatoryPan = this.application.signatory.pan.trim().toUpperCase();
      if (!this.signatoryIsOwner && this.ubos.every((u) => u.pan.trim().toUpperCase() === signatoryPan)) {
        this.error.set('Add at least one owner who is not the authorised signatory.');
        return;
      }
      if (!this.frozen) {
        this.error.set('Confirm the beneficial owner list to freeze it.');
        return;
      }
    }
    this.save.emit({
      ...this.payload(),
      currentStep: nextOnboardingStep('ubo', this.application.profile.entityType, this.application.signatoryIsOwner),
    });
  }

  private seedFromRegistryDirectors(): void {
    if (this.ubos.length) {
      return;
    }
    const directors = this.application.registryDirectors ?? [];
    if (!directors.length) {
      return;
    }
    this.ubos = directors.map((d) => ({
      id: d.din || crypto.randomUUID(),
      name: d.name,
      pan: d.pan || '',
      ownershipPercent: 0,
      relationship: d.designation || 'Director',
      kycVerified: false,
      mobile: '',
      digiConsent: false,
    }));
  }

  private payload(): KycApplication {
    return {
      ...this.application,
      ubos: this.ubos.map(({ mobile, digiConsent, digilocker, ...ubo }) => ubo),
      ubosFrozen: this.frozen,
      publicListedSkip: this.skipListed,
      registryDirectors: this.application.registryDirectors,
    };
  }
}
