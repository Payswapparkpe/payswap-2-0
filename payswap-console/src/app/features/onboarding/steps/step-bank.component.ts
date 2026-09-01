import { Component, ElementRef, EventEmitter, Input, OnInit, Output, ViewChild, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { KycApplication, UploadedDoc } from '../../../core/models/onboarding.models';
import { ifsc } from '../../../core/validators/india.validators';
import { FileDropzoneComponent } from '../../../shared/ui/file-dropzone/file-dropzone.component';
import { InlineAlertComponent } from '../../../shared/ui/inline-alert/inline-alert.component';
import { VerificationService } from '../../../core/services/verification.service';
import { nextOnboardingStep, prevOnboardingStep, allowedAccountTypes, isAllowedAccountType, rulesFor } from '../../../core/config/entity-rules';
import { scrollToFeedback } from '../../../core/utils/feedback.util';
import { isVerificationLocked } from '../../../core/utils/verification-lock.util';

@Component({
  selector: 'app-step-bank',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    FileDropzoneComponent,
    InlineAlertComponent,
  ],
  template: `
    <form [formGroup]="form">
      <p class="warn">{{ bankHint }}</p>
      <div class="grid">
        <mat-form-field appearance="outline">
          <mat-label>Account holder name</mat-label>
          <input matInput formControlName="holderName" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Account number</mat-label>
          <input matInput formControlName="accountNumber" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>IFSC</mat-label>
          <input matInput formControlName="ifsc" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Account type</mat-label>
          <mat-select formControlName="accountType">
            @for (type of accountTypes; track type) {
              <mat-option [value]="type">{{ type === 'savings' ? 'Savings' : 'Current' }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </div>
      <div class="row">
        <button mat-stroked-button type="button" (click)="lookup()" [disabled]="looking()">
          {{ looking() ? 'Looking up IFSC…' : 'Lookup IFSC' }}
        </button>
        @if (!pennyLocked()) {
          <button mat-stroked-button type="button" (click)="penny()" [disabled]="dropping()">
            {{ dropping() ? 'Sending ₹1…' : 'Verify with ₹1 penny drop' }}
          </button>
        }
      </div>
      @if (form.controls.bankName.value) {
        <p>{{ form.controls.bankName.value }} · {{ form.controls.branch.value }}</p>
      }

      @if (ifscAlert(); as alert) {
        <app-inline-alert [message]="alert" tone="error" />
      }

      @if (status() === 'matched') {
        <app-inline-alert message="Penny drop matched. Bank account name confirmed." tone="success" />
      }

      @if (status() === 'mismatch') {
        <app-inline-alert [message]="mismatchMessage()" tone="info" />
        <app-file-dropzone
          label="Bank proof"
          hint="Upload cancelled cheque, statement, or bank letter showing the account holder name."
          slotId="penny_proof"
          [value]="proof"
          (valueChange)="onProofChange($event)"
        />
      }

      @if (submitError()) {
        <div #submitFeedback>
          <app-inline-alert [message]="submitError()" tone="error" />
        </div>
      }

      <div class="actions">
        <button mat-button type="button" (click)="back()">Back</button>
        <button mat-flat-button color="primary" type="button" (click)="next()">Save and continue</button>
      </div>
    </form>
  `,
  styles: [
    `
      .warn {
        background: #fff4e5;
        color: #9a4b00;
        padding: 10px 12px;
        border-radius: 10px;
      }
      .grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 4px 16px;
      }
      .row {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin: 12px 0;
      }
      .actions {
        display: flex;
        justify-content: space-between;
        margin-top: 16px;
      }
      @media (max-width: 720px) {
        .grid {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class StepBankComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly verification = inject(VerificationService);

  @Input({ required: true }) application!: KycApplication;
  @Input() readonly = false;
  @Output() save = new EventEmitter<KycApplication>();

  @ViewChild('submitFeedback') submitFeedback?: ElementRef<HTMLElement>;

  readonly looking = signal(false);
  readonly dropping = signal(false);
  readonly status = signal(this.application?.bank.pennyDropStatus ?? 'idle');
  readonly ifscAlert = signal('');
  readonly submitError = signal('');
  readonly mismatchMessage = signal(
    'Bank account name does not match the entity legal name. Correct the holder name or upload bank proof below.',
  );
  proof?: UploadedDoc;

  readonly form = this.fb.nonNullable.group({
    holderName: ['', Validators.required],
    accountNumber: ['', [Validators.required, Validators.minLength(8)]],
    ifsc: ['', [Validators.required, ifsc()]],
    accountType: ['current' as 'current' | 'savings', Validators.required],
    bankName: [''],
    branch: [''],
  });

  ngOnInit(): void {
    const types = this.accountTypes;
    const savedType = this.application.bank.accountType;
    const defaultType = types.includes(savedType) ? savedType : types[0];
    const expectedName =
      rulesFor(this.application.profile.entityType)?.bankMatches === 'person'
        ? this.application.signatory.name
        : this.application.profile.legalName;
    this.form.patchValue({
      ...this.application.bank,
      accountType: defaultType,
      holderName: this.application.bank.holderName || expectedName,
    });
    this.status.set(this.application.bank.pennyDropStatus);
    this.proof = this.application.bank.proofFile;
    this.syncBankFieldLock();
    if (this.readonly) {
      this.form.disable({ emitEvent: false });
    }
  }

  get accountTypes(): Array<'current' | 'savings'> {
    return allowedAccountTypes(this.application.profile.entityType);
  }

  pennyLocked(): boolean {
    return isVerificationLocked(this.status() === 'matched', this.application, 'bank');
  }

  private syncBankFieldLock(): void {
    if (this.readonly) {
      return;
    }
    const lock = this.pennyLocked();
    (['holderName', 'accountNumber', 'ifsc', 'accountType'] as const).forEach((field) => {
      const control = this.form.controls[field];
      if (lock) {
        control.disable({ emitEvent: false });
      } else {
        control.enable({ emitEvent: false });
      }
    });
  }

  lookup(): void {
    const code = this.form.controls.ifsc.value.toUpperCase();
    this.form.controls.ifsc.setValue(code);
    if (this.form.controls.ifsc.invalid) {
      this.form.controls.ifsc.markAsTouched();
      return;
    }
    this.looking.set(true);
    this.ifscAlert.set('');
    this.verification.verifyIfsc(code).subscribe({
      next: (result) => {
        this.looking.set(false);
        this.form.patchValue({ bankName: result.bankName, branch: result.branch });
      },
      error: (err: Error) => {
        this.looking.set(false);
        this.ifscAlert.set(err.message || 'IFSC lookup failed.');
      },
    });
  }

  penny(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.dropping.set(true);
    this.submitError.set('');
    this.ifscAlert.set('');
    this.status.set('sent');
    this.verification
      .verifyBankAccount(
        this.form.controls.accountNumber.value,
        this.form.controls.holderName.value,
        this.form.controls.ifsc.value,
      )
      .subscribe({
        next: (result) => {
          this.dropping.set(false);
          this.status.set(result.status);
          if (result.status === 'matched') {
            this.submitError.set('');
            this.syncBankFieldLock();
            return;
          }
          if (result.status === 'mismatch') {
            const detail =
              result.expectedName && result.matchedName
                ? `Bank returned "${result.matchedName}" but we expected "${result.expectedName}". Update the holder name or upload bank proof.`
                : 'Bank account name does not match the entity legal name. Update the holder name or upload bank proof.';
            this.mismatchMessage.set(detail);
          }
        },
        error: (err: Error) => {
          this.dropping.set(false);
          this.status.set('idle');
          this.submitError.set(err.message || 'Bank verification failed.');
          scrollToFeedback(this.submitFeedback?.nativeElement);
        },
      });
  }

  onProofChange(file?: UploadedDoc): void {
    this.proof = file;
    if (file) {
      this.submitError.set('');
    }
  }

  back(): void {
    this.save.emit({
      ...this.payload(),
      currentStep: prevOnboardingStep('bank', this.application.profile.entityType, this.application.signatoryIsOwner),
    });
  }

  next(): void {
    this.submitError.set('');
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.submitError.set('Complete all bank fields before continuing.');
      scrollToFeedback(this.submitFeedback?.nativeElement);
      return;
    }
    const selected = this.form.controls.accountType.value;
    if (!isAllowedAccountType(this.application.profile.entityType, selected)) {
      this.form.controls.accountType.setValue(this.accountTypes[0]);
    }
    if (this.status() !== 'matched' && !(this.status() === 'mismatch' && this.proof)) {
      this.submitError.set('Run penny drop verification first. If names mismatch, upload bank proof.');
      scrollToFeedback(this.submitFeedback?.nativeElement);
      return;
    }
    this.save.emit({
      ...this.payload(),
      currentStep: nextOnboardingStep('bank', this.application.profile.entityType, this.application.signatoryIsOwner),
    });
  }

  get bankHint(): string {
    return (
      rulesFor(this.application.profile.entityType)?.bankHolderHint ||
      'The account name must match PAN and GST legal name exactly — the most common cause of rejection.'
    );
  }

  private payload(): KycApplication {
    const value = this.form.getRawValue();
    return {
      ...this.application,
      bank: {
        ...value,
        pennyDropStatus: this.status() === 'matched' || this.status() === 'mismatch' ? this.status() : 'idle',
        proofFile: this.proof,
      },
    };
  }
}
