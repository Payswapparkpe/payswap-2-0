import { Component, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { DigilockerSnapshot, KycApplication, UploadedDoc } from '../../../core/models/onboarding.models';
import { indianMobile as mobileValidator, pan as panValidator } from '../../../core/validators/india.validators';
import { FileDropzoneComponent } from '../../../shared/ui/file-dropzone/file-dropzone.component';
import { VerificationService } from '../../../core/services/verification.service';
import { nextOnboardingStep, prevOnboardingStep } from '../../../core/config/entity-rules';

@Component({
  selector: 'app-step-owner',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule,
    FileDropzoneComponent,
  ],
  template: `
    <form [formGroup]="form">
      <p class="lede">
        You are onboarding as the authorised signatory, not as a business owner. Complete identity
        verification for a director, partner, or beneficial owner who holds ownership or control of
        this entity. Payswap reviews this file before KYB approval.
      </p>
      <div class="grid">
        <mat-form-field appearance="outline">
          <mat-label>Owner full name</mat-label>
          <input matInput formControlName="name" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Owner personal PAN</mat-label>
          <input matInput formControlName="pan" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Date of birth</mat-label>
          <input matInput type="date" formControlName="dob" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Mobile linked to DigiLocker</mat-label>
          <input matInput formControlName="mobile" maxlength="10" />
        </mat-form-field>
      </div>

      <div class="panel">
        <h4>Owner DigiLocker</h4>
        <p>Consent-based fetch of Aadhaar, PAN, and driving licence for the business owner. Demo: PAN ending in 9 has no DigiLocker account.</p>
        <mat-checkbox formControlName="digiConsent">
          The owner allows Payswap to receive Aadhaar, PAN, and driving licence from DigiLocker
        </mat-checkbox>
        <div class="row">
          <button
            mat-stroked-button
            type="button"
            (click)="startDigilocker()"
            [disabled]="!form.controls.digiConsent.value || busy()"
          >
            {{ busy() ? lockerLabel() : lockerCta() }}
          </button>
        </div>
        @if (snapshot(); as session) {
          <p class="ok">DigiLocker {{ session.status.toLowerCase().replace('_', ' ') }}.</p>
          @for (doc of session.documents; track doc.type) {
            <p class="fetched">{{ doc.type }} · {{ doc.name }} · {{ doc.idMasked }}</p>
          }
        }
      </div>

      <div class="uploads">
        <h4>Owner identity documents</h4>
        <p>Upload colour scans of the owner’s documents. PDF, JPG, or PNG, max 2 MB.</p>
        <app-file-dropzone
          label="Owner PAN card"
          hint="Personal PAN of the director, partner, or beneficial owner."
          slotId="owner_pan"
          [value]="doc('owner_pan')"
          (valueChange)="setDoc($event, 'owner_pan')"
        />
        <app-file-dropzone
          label="Owner photo ID"
          hint="Aadhaar (masked), passport, voter ID, or driving licence."
          slotId="owner_id"
          [value]="doc('owner_id')"
          (valueChange)="setDoc($event, 'owner_id')"
        />
      </div>

      @if (verified()) {
        <p class="ok">Business owner identity verified. Continue with entity KYB and the board resolution.</p>
      }
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }

      <div class="actions">
        <button mat-button type="button" (click)="back()">Back</button>
        <button mat-flat-button color="primary" type="button" (click)="next()" [disabled]="!verified()">
          Save and continue
        </button>
      </div>
    </form>
  `,
  styles: [
    `
      .lede {
        color: #6d6484;
      }
      .grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 4px 16px;
      }
      .panel,
      .uploads {
        display: grid;
        gap: 12px;
        padding: 16px;
        border-radius: 14px;
        background: #f7f4ff;
        margin-bottom: 14px;
      }
      .row {
        display: flex;
        gap: 10px;
      }
      .ok {
        color: #0f7a3d;
        font-weight: 650;
      }
      .fetched {
        margin: 0;
        font-size: 13px;
        color: #3d3554;
      }
      .error {
        color: #b42318;
      }
      .actions {
        display: flex;
        justify-content: space-between;
        margin-top: 8px;
      }
      @media (max-width: 720px) {
        .grid {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class StepOwnerComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly verification = inject(VerificationService);

  @Input({ required: true }) application!: KycApplication;
  @Output() save = new EventEmitter<KycApplication>();

  readonly busy = signal(false);
  readonly lockerLabel = signal('Connecting…');
  readonly verified = signal(false);
  readonly error = signal('');
  readonly snapshot = signal<DigilockerSnapshot | null>(null);
  docs: UploadedDoc[] = [];

  readonly form = this.fb.nonNullable.group({
    name: ['', Validators.required],
    pan: ['', [Validators.required, panValidator()]],
    dob: [''],
    mobile: ['', [Validators.required, mobileValidator()]],
    digiConsent: [false],
  });

  ngOnInit(): void {
    const s = this.application.ownerKyc;
    this.form.patchValue({
      name: s.name,
      pan: s.pan,
      dob: s.dob,
      mobile: s.mobile,
    });
    this.docs = [...s.docs];
    this.snapshot.set(s.digilocker ?? null);
    this.verified.set(s.verified);
  }

  lockerCta(): string {
    if (!this.snapshot()) {
      return 'Verify owner DigiLocker account';
    }
    if (this.snapshot()?.status === 'PENDING') {
      return 'Complete DigiLocker consent';
    }
    return 'Refresh DigiLocker documents';
  }

  doc(slotId: string): UploadedDoc | undefined {
    return this.docs.find((d) => d.slotId === slotId);
  }

  setDoc(file: UploadedDoc | undefined, slotId: string): void {
    this.docs = this.docs.filter((d) => d.slotId !== slotId);
    if (file) {
      this.docs.push({ ...file, slotId });
    }
    this.syncVerified();
  }

  startDigilocker(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.error.set('');
    this.busy.set(true);
    const pan = this.form.controls.pan.value;
    const mobile = this.form.controls.mobile.value;
    const name = this.form.controls.name.value;

    this.lockerLabel.set('Checking DigiLocker account…');
    this.verification.verifyDigilockerAccount(mobile, pan).subscribe((account) => {
      if (account.status === 'ACCOUNT_NOT_FOUND') {
        this.busy.set(false);
        this.snapshot.set(null);
        this.verified.set(false);
        this.error.set('No DigiLocker account for this mobile / PAN. Demo: avoid PAN ending in 9.');
        return;
      }
      this.lockerLabel.set('Opening consent…');
      this.verification.createDigilockerUrl(account.verificationId).subscribe((url) => {
        this.snapshot.set({
          verificationId: url.verificationId,
          referenceId: url.referenceId,
          status: url.status,
          documents: [],
        });
        this.lockerLabel.set('Fetching documents…');
        this.verification.getDigilockerStatus(url.verificationId, pan, name).subscribe((status) => {
          this.busy.set(false);
          this.snapshot.set(status);
          if (status.status !== 'AUTHENTICATED') {
            this.verified.set(false);
            this.error.set('DigiLocker consent was not completed.');
            return;
          }
          const panDoc = status.documents.find((d) => d.type === 'PAN');
          if (panDoc?.name) {
            this.form.controls.name.setValue(panDoc.name);
          }
          this.syncVerified();
        });
      });
    });
  }

  back(): void {
    this.save.emit({
      ...this.payload(),
      currentStep: prevOnboardingStep(
        'owner',
        this.application.profile.entityType,
        this.application.signatoryIsOwner,
      ),
    });
  }

  next(): void {
    if (!this.verified()) {
      return;
    }
    this.save.emit({
      ...this.payload(),
      currentStep: nextOnboardingStep(
        'owner',
        this.application.profile.entityType,
        this.application.signatoryIsOwner,
      ),
    });
  }

  private syncVerified(): void {
    const lockerOk = this.snapshot()?.status === 'AUTHENTICATED';
    const filesOk = !!this.doc('owner_pan') && !!this.doc('owner_id');
    this.verified.set(!!lockerOk && filesOk);
    if (lockerOk && !filesOk) {
      this.error.set('Upload the owner PAN and a photo ID to finish owner KYC.');
    } else if (this.verified()) {
      this.error.set('');
    }
  }

  private payload(): KycApplication {
    const value = this.form.getRawValue();
    return {
      ...this.application,
      ownerKyc: {
        name: value.name,
        pan: value.pan.toUpperCase(),
        dob: value.dob,
        mobile: value.mobile,
        path: 'digilocker',
        verified: this.verified(),
        digilockerFailed: this.snapshot()?.status === 'FAILED' || this.snapshot()?.status === 'ACCOUNT_NOT_FOUND',
        digilocker: this.snapshot(),
        address: this.application.ownerKyc.address,
        docs: this.docs,
      },
    };
  }
}
