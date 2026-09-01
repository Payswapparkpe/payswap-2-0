import { Component, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatSelectModule } from '@angular/material/select';
import { DigilockerSnapshot, ENTITY_LABELS, EntityType, KycApplication, UploadedDoc } from '../../../core/models/onboarding.models';
import { relationsFor } from '../../../core/config/signatory-relations';
import { indianMobile as mobileValidator, pan as panValidator } from '../../../core/validators/india.validators';
import { FileDropzoneComponent } from '../../../shared/ui/file-dropzone/file-dropzone.component';
import { VerificationService } from '../../../core/services/verification.service';

@Component({
  selector: 'app-step-signatory',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatCheckboxModule,
    MatSelectModule,
    FileDropzoneComponent,
  ],
  template: `
    <form [formGroup]="form">
      <p class="lede">
        Select the entity type first. Confirm whether you are the authorised signatory, then complete
        person KYC. Payswap admin approves KYC and KYB after you submit.
      </p>
      <mat-form-field appearance="outline" class="full">
        <mat-label>Entity type</mat-label>
        <mat-select formControlName="entityType" (selectionChange)="onEntityChange()">
          @for (item of entities; track item.id) {
            <mat-option [value]="item.id">{{ item.label }}</mat-option>
          }
        </mat-select>
      </mat-form-field>

      @if (form.controls.entityType.value) {
        <div class="panel">
          <mat-checkbox formControlName="kycPersonIsAuthorisedSignatory">
            The person completing this KYC is the authorised signatory for the business
          </mat-checkbox>
          <mat-form-field appearance="outline" class="full">
            <mat-label>Authorised signatory’s relation to the business</mat-label>
            <mat-select formControlName="signatoryRelation">
              @for (rel of relations; track rel.id) {
                <mat-option [value]="rel.id">{{ rel.label }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          @if (!form.controls.kycPersonIsAuthorisedSignatory.value) {
            <mat-form-field appearance="outline" class="full">
              <mat-label>Authorised signatory’s full name</mat-label>
              <input matInput formControlName="authorisedSignatoryName" />
            </mat-form-field>
            <p class="note">
              Complete your own KYC below. The authorised signatory named here is recorded on the
              file for admin review, together with the board resolution appointing them.
            </p>
          }
        </div>
      }

      <h4>Person KYC</h4>
      <div class="grid">
        <mat-form-field appearance="outline">
          <mat-label>Full name</mat-label>
          <input matInput formControlName="name" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Personal PAN</mat-label>
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
        <h4>DigiLocker</h4>
        <p>Consent-based fetch of Aadhaar, PAN, and driving licence. Demo: PAN ending in 9 has no DigiLocker account.</p>
        <mat-checkbox formControlName="digiConsent">
          I allow Payswap to receive Aadhaar, PAN, and driving licence from DigiLocker for KYC
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
        <h4>Physical documents</h4>
        <p>Upload clear colour scans even after DigiLocker succeeds. PDF, JPG, or PNG, max 2 MB.</p>
        <app-file-dropzone
          label="PAN card"
          hint="Physical PAN card, both sides if needed."
          slotId="signatory_pan"
          [value]="doc('signatory_pan')"
          (valueChange)="setDoc($event, 'signatory_pan')"
        />
        <app-file-dropzone
          label="Aadhaar / Passport / Voter ID / Driving licence"
          hint="Photo identity with address. Mask Aadhaar if sharing a scan."
          slotId="signatory_id"
          [value]="doc('signatory_id')"
          (valueChange)="setDoc($event, 'signatory_id')"
        />
      </div>

      @if (verified()) {
        <p class="ok">Identity verified via DigiLocker and physical documents.</p>
      }
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }

      <div class="actions">
        <span></span>
        <button mat-flat-button color="primary" type="button" (click)="next()" [disabled]="!verified()">
          Save and continue
        </button>
      </div>
    </form>
  `,
  styles: [
    `
      .lede,
      .note {
        color: #6d6484;
      }
      .full {
        width: 100%;
      }
      .note {
        margin: 0;
        font-size: 13px;
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
export class StepSignatoryComponent implements OnInit {
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
  private verificationId = '';

  readonly entities = (Object.keys(ENTITY_LABELS) as EntityType[]).map((id) => ({
    id,
    label: ENTITY_LABELS[id],
  }));

  readonly form = this.fb.nonNullable.group({
    entityType: ['' as EntityType | '', Validators.required],
    kycPersonIsAuthorisedSignatory: [true],
    signatoryRelation: [''],
    authorisedSignatoryName: [''],
    name: ['', Validators.required],
    pan: ['', [Validators.required, panValidator()]],
    dob: [''],
    mobile: ['', [Validators.required, mobileValidator()]],
    digiConsent: [false],
  });

  get relations() {
    return relationsFor(this.form.controls.entityType.value);
  }

  ngOnInit(): void {
    const s = this.application.signatory;
    this.form.patchValue({
      entityType: this.application.profile.entityType,
      kycPersonIsAuthorisedSignatory: this.application.kycPersonIsAuthorisedSignatory !== false,
      signatoryRelation: this.application.signatoryRelation,
      authorisedSignatoryName: this.application.authorisedSignatoryName,
      name: s.name,
      pan: s.pan,
      dob: s.dob,
      mobile: s.mobile,
    });
    this.docs = [...s.docs];
    this.snapshot.set(s.digilocker ?? null);
    this.verified.set(s.verified);
  }

  onEntityChange(): void {
    const type = this.form.controls.entityType.value;
    const rels = relationsFor(type);
    if (type === 'individual') {
      this.form.controls.kycPersonIsAuthorisedSignatory.setValue(true);
      this.form.controls.signatoryRelation.setValue('self');
    } else if (!rels.some((r) => r.id === this.form.controls.signatoryRelation.value)) {
      this.form.controls.signatoryRelation.setValue(rels[0]?.id ?? '');
    }
    this.save.emit({
      ...this.application,
      currentStep: 'signatory',
      profile: { ...this.application.profile, entityType: type },
      kycPersonIsAuthorisedSignatory: this.form.controls.kycPersonIsAuthorisedSignatory.value,
      signatoryRelation: this.form.controls.signatoryRelation.value,
      authorisedSignatoryName: this.form.controls.authorisedSignatoryName.value,
    });
  }

  lockerCta(): string {
    if (!this.snapshot()) {
      return 'Verify DigiLocker account';
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
      this.verificationId = account.verificationId;
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

  next(): void {
    if (!this.form.controls.entityType.value) {
      this.form.controls.entityType.markAsTouched();
      this.error.set('Select the entity type to continue.');
      return;
    }
    if (!this.form.controls.signatoryRelation.value) {
      this.form.controls.signatoryRelation.markAsTouched();
      this.error.set('Select the authorised signatory’s relation to the business.');
      return;
    }
    if (!this.form.controls.kycPersonIsAuthorisedSignatory.value && !this.form.controls.authorisedSignatoryName.value.trim()) {
      this.error.set('Enter the authorised signatory’s name, or confirm that you are the authorised signatory.');
      return;
    }
    if (!this.verified()) {
      return;
    }
    this.save.emit({ ...this.payload(), currentStep: 'profile' });
  }

  private syncVerified(): void {
    const lockerOk = this.snapshot()?.status === 'AUTHENTICATED';
    const filesOk = !!this.doc('signatory_pan') && !!this.doc('signatory_id');
    this.verified.set(!!lockerOk && filesOk);
    if (lockerOk && !filesOk) {
      this.error.set('Upload PAN and a photo ID to finish KYC.');
    } else if (this.verified()) {
      this.error.set('');
    }
  }

  private payload(): KycApplication {
    const value = this.form.getRawValue();
    const same = value.kycPersonIsAuthorisedSignatory;
    return {
      ...this.application,
      kycPersonIsAuthorisedSignatory: same,
      signatoryRelation: value.signatoryRelation,
      authorisedSignatoryName: same ? value.name : value.authorisedSignatoryName,
      profile: {
        ...this.application.profile,
        entityType: value.entityType,
      },
      signatory: {
        name: value.name,
        pan: value.pan.toUpperCase(),
        dob: value.dob,
        mobile: value.mobile,
        path: 'digilocker',
        verified: this.verified(),
        digilockerFailed: this.snapshot()?.status === 'FAILED' || this.snapshot()?.status === 'ACCOUNT_NOT_FOUND',
        digilocker: this.snapshot(),
        address: this.application.signatory.address,
        docs: this.docs,
      },
    };
  }
}
