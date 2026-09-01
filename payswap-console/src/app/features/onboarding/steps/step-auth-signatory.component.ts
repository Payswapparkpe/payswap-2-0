import { Component, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { DigilockerSnapshot, KycApplication, UploadedDoc } from '../../../core/models/onboarding.models';
import { indianMobile as mobileValidator, pan as panValidator } from '../../../core/validators/india.validators';
import { DigilockerSessionService } from '../../../core/services/digilocker-session.service';
import { onboardingNav } from '../../../core/config/entity-rules';
import { isVerificationLocked } from '../../../core/utils/verification-lock.util';
import { FileDropzoneComponent } from '../../../shared/ui/file-dropzone/file-dropzone.component';

@Component({
  selector: 'app-step-auth-signatory',
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
        You are opening this account on behalf of the business. Complete Aadhaar and PAN verification for
        <strong>{{ application.authorisedSignatoryName || 'the authorised signatory' }}</strong> — required
        together with the board resolution or letter of authority.
      </p>
      <div class="grid">
        <mat-form-field appearance="outline">
          <mat-label>Authorised signatory name</mat-label>
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
        <h4>Verify via DigiLocker</h4>
        @if (!lockerLocked()) {
          <mat-checkbox formControlName="digiConsent">
            The signatory allows Payswap to receive Aadhaar and PAN from DigiLocker
          </mat-checkbox>
          <button
            mat-stroked-button
            type="button"
            (click)="startDigilocker()"
            [disabled]="!form.controls.digiConsent.value || busy()"
          >
            {{ busy() ? lockerLabel() : 'Verify with DigiLocker' }}
          </button>
        }
        @if (snapshot(); as session) {
          @for (doc of session.documents; track doc.type) {
            <p class="fetched">{{ doc.type }} · {{ doc.name }} · {{ doc.idMasked }}</p>
          }
        }
      </div>

      @if (!lockerLocked()) {
      <div class="panel alt">
        <h4>Or upload self-attested copies</h4>
        <p class="hint">Signed Aadhaar and PAN copies. OCR extracts details and stores them on the file.</p>
        <app-file-dropzone
          label="Self-attested Aadhaar"
          hint="PDF or image with signature."
          slotId="auth_signatory_aadhaar"
          [value]="doc('auth_signatory_aadhaar')"
          (valueChange)="setDoc($event, 'auth_signatory_aadhaar')"
        />
        <app-file-dropzone
          label="Self-attested PAN"
          hint="PDF or image with signature."
          slotId="auth_signatory_pan"
          [value]="doc('auth_signatory_pan')"
          (valueChange)="setDoc($event, 'auth_signatory_pan')"
        />
      </div>
      }

      @if (verified() && lockerLocked()) {
        <p class="ok">Authorised signatory identity verified.</p>
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
        line-height: 1.5;
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
        margin: 14px 0;
      }
      .panel.alt {
        background: #f4f8ff;
      }
      .hint {
        margin: 0;
        font-size: 13px;
        color: #6d6484;
      }
      .ok {
        color: #0f7a3d;
        font-weight: 650;
      }
      .fetched {
        margin: 0;
        font-size: 13px;
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
export class StepAuthSignatoryComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
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
    name: [
      '',
      Validators.required,
    ],
    pan: ['', [Validators.required, panValidator()]],
    dob: [''],
    mobile: ['', [Validators.required, mobileValidator()]],
    digiConsent: [false],
  });

  lockerLocked(): boolean {
    return isVerificationLocked(this.verified(), this.application, 'auth_signatory');
  }

  ngOnInit(): void {
    const seed = this.application.authSignatoryKyc;
    this.form.patchValue({
      name: seed?.name || this.application.authorisedSignatoryName || '',
      pan: seed?.pan || '',
      dob: seed?.dob || '',
      mobile: seed?.mobile || '',
    });
    this.docs = [...(seed?.docs ?? [])];
    this.snapshot.set(seed?.digilocker ?? null);
    this.verified.set(!!seed?.verified);
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

  doc(slotId: string): UploadedDoc | undefined {
    return this.docs.find((d) => d.slotId === slotId);
  }

  setDoc(file: UploadedDoc | undefined, slotId: string): void {
    this.docs = this.docs.filter((d) => d.slotId !== slotId);
    if (file) {
      this.docs.push({
        ...file,
        slotId,
        ocrPayload: file.ocrPayload ?? { status: 'pending', source: slotId },
      });
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
    this.lockerLabel.set('Opening DigiLocker…');
    this.digilockerSession
      .run({
        mobile: this.form.controls.mobile.value,
        pan: this.form.controls.pan.value,
        name: this.form.controls.name.value,
      })
      .subscribe({
        next: (status) => {
          this.busy.set(false);
          this.snapshot.set(status);
          if (status.status !== 'AUTHENTICATED') {
            this.verified.set(false);
            this.error.set('DigiLocker verification did not complete.');
            return;
          }
          const verifiedName = status.userDetails?.name || status.documents.find((d) => d.type === 'AADHAAR')?.name;
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
    this.save.emit({ ...this.payload(), currentStep: onboardingNav(this.application).prev('auth_signatory') });
  }

  next(): void {
    if (!this.verified()) {
      return;
    }
    this.save.emit({ ...this.payload(), currentStep: onboardingNav(this.application).next('auth_signatory') });
  }

  private syncVerified(): void {
    const lockerOk = this.snapshot()?.status === 'AUTHENTICATED';
    const selfAttestedOk =
      this.docs.some((d) => d.slotId === 'auth_signatory_aadhaar') &&
      this.docs.some((d) => d.slotId === 'auth_signatory_pan');
    this.verified.set(!!lockerOk || selfAttestedOk);
    this.applyFieldLocks();
  }

  private payload(): KycApplication {
    const value = this.form.getRawValue();
    const lockerOk = this.snapshot()?.status === 'AUTHENTICATED';
    const selfAttestedOk =
      this.docs.some((d) => d.slotId === 'auth_signatory_aadhaar') &&
      this.docs.some((d) => d.slotId === 'auth_signatory_pan');
    return {
      ...this.application,
      authSignatoryKyc: {
        name: value.name,
        pan: value.pan.toUpperCase(),
        dob: value.dob,
        mobile: value.mobile,
        path: lockerOk ? 'digilocker' : 'self_attested',
        verified: this.verified(),
        digilockerFailed: this.snapshot()?.status === 'FAILED',
        digilocker: this.snapshot(),
        address: this.application.authSignatoryKyc?.address ?? this.application.signatory.address,
        docs: this.docs,
      },
    };
  }
}
