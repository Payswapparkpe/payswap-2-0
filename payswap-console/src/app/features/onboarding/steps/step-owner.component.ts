import { Component, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { DigilockerSnapshot, KycApplication, UploadedDoc } from '../../../core/models/onboarding.models';
import { indianMobile as mobileValidator, pan as panValidator } from '../../../core/validators/india.validators';
import { VerificationService } from '../../../core/services/verification.service';
import { DigilockerSessionService } from '../../../core/services/digilocker-session.service';
import { isVerificationLocked } from '../../../core/utils/verification-lock.util';
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
        @if (!lockerLocked()) {
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
        }
        @if (snapshot(); as session) {
          <p class="ok">DigiLocker {{ session.status.toLowerCase().replace('_', ' ') }}.</p>
          @for (doc of session.documents; track doc.type) {
            <p class="fetched">{{ doc.type }} · {{ doc.name }} · {{ doc.idMasked }}</p>
          }
        }
      </div>

      @if (verified() && lockerLocked()) {
        <p class="ok">Business owner identity verified via DigiLocker.</p>
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
      .panel {
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
  private readonly digilockerSession = inject(DigilockerSessionService);

  @Input({ required: true }) application!: KycApplication;
  @Input() readonly = false;
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

  lockerLocked(): boolean {
    return isVerificationLocked(this.verified(), this.application, 'owner');
  }

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
    this.applyFieldLocks();
  }

  private applyFieldLocks(): void {
    if (this.readonly) {
      this.form.disable({ emitEvent: false });
      return;
    }
    const lock = this.lockerLocked();
    (['name', 'pan', 'dob', 'mobile', 'digiConsent'] as const).forEach((field) => {
      const control = this.form.get(field);
      if (lock) {
        control?.disable({ emitEvent: false });
      } else {
        control?.enable({ emitEvent: false });
      }
    });
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

    this.lockerLabel.set('Opening DigiLocker…');
    this.digilockerSession.run({ mobile, pan, name }).subscribe({
      next: (status) => {
        this.busy.set(false);
        this.snapshot.set(status);
        if (status.status !== 'AUTHENTICATED') {
          this.verified.set(false);
          this.error.set('DigiLocker verification did not complete.');
          return;
        }
        const idDoc =
          status.documents.find((d) => d.type === 'PAN') ?? status.documents.find((d) => d.type === 'AADHAAR');
        const verifiedName = status.userDetails?.name || idDoc?.name;
        if (verifiedName) {
          this.form.controls.name.setValue(verifiedName);
        }
        this.syncVerified();
      },
      error: (err: Error) => {
        this.busy.set(false);
        this.error.set(err.message || 'DigiLocker verification failed.');
      },
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
    this.verified.set(!!lockerOk);
    if (this.verified()) {
      this.error.set('');
    }
    this.applyFieldLocks();
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
