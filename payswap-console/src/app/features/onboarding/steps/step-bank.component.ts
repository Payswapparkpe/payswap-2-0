import { Component, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { KycApplication, UploadedDoc } from '../../../core/models/onboarding.models';
import { ifsc } from '../../../core/validators/india.validators';
import { FileDropzoneComponent } from '../../../shared/ui/file-dropzone/file-dropzone.component';
import { VerificationService } from '../../../core/services/verification.service';
import { nextOnboardingStep, prevOnboardingStep, allowedAccountType, rulesFor } from '../../../core/config/entity-rules';

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
            @if (accountType === 'savings') {
              <mat-option value="savings">Savings</mat-option>
            } @else {
              <mat-option value="current">Current</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </div>
      <div class="row">
        <button mat-stroked-button type="button" (click)="lookup()" [disabled]="looking()">
          {{ looking() ? 'Looking up IFSC…' : 'Lookup IFSC' }}
        </button>
        <button mat-stroked-button type="button" (click)="penny()" [disabled]="dropping()">
          {{ dropping() ? 'Sending ₹1…' : 'Verify with ₹1 penny drop' }}
        </button>
      </div>
      @if (form.controls.bankName.value) {
        <p>{{ form.controls.bankName.value }} · {{ form.controls.branch.value }}</p>
      }
      @if (status() === 'matched') {
        <p class="ok">Penny drop matched. Name confirmed.</p>
      }
      @if (status() === 'mismatch') {
        <p class="error">Penny drop name mismatch. Upload a cancelled cheque, statement, or bank letter. Demo: avoid account numbers ending in 0.</p>
        <app-file-dropzone
          label="Bank proof"
          slotId="penny_proof"
          [value]="proof"
          (valueChange)="proof = $event"
        />
      }
      @if (error()) {
        <p class="error">{{ error() }}</p>
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
        margin-bottom: 12px;
      }
      .ok {
        color: #0f7a3d;
        font-weight: 650;
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
  @Output() save = new EventEmitter<KycApplication>();

  readonly looking = signal(false);
  readonly dropping = signal(false);
  readonly status = signal(this.application?.bank.pennyDropStatus ?? 'idle');
  readonly error = signal('');
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
    const type = this.accountType;
    const expectedName =
      rulesFor(this.application.profile.entityType)?.bankMatches === 'person'
        ? this.application.signatory.name
        : this.application.profile.legalName;
    this.form.patchValue({
      ...this.application.bank,
      accountType: type,
      holderName: this.application.bank.holderName || expectedName,
    });
    this.status.set(this.application.bank.pennyDropStatus);
    this.proof = this.application.bank.proofFile;
  }

  get accountType(): 'current' | 'savings' {
    return allowedAccountType(this.application.profile.entityType);
  }

  lookup(): void {
    const code = this.form.controls.ifsc.value.toUpperCase();
    this.form.controls.ifsc.setValue(code);
    if (this.form.controls.ifsc.invalid) {
      this.form.controls.ifsc.markAsTouched();
      return;
    }
    this.looking.set(true);
    this.verification.verifyIfsc(code).subscribe((result) => {
      this.looking.set(false);
      this.form.patchValue({ bankName: result.bankName, branch: result.branch });
    });
  }

  penny(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.dropping.set(true);
    this.status.set('sent');
    this.verification
      .verifyBankAccount(this.form.controls.accountNumber.value, this.form.controls.holderName.value)
      .subscribe((result) => {
        this.dropping.set(false);
        this.status.set(result.status);
      });
  }

  back(): void {
    this.save.emit({
      ...this.payload(),
      currentStep: prevOnboardingStep('bank', this.application.profile.entityType, this.application.signatoryIsOwner),
    });
  }

  next(): void {
    this.error.set('');
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    if (this.form.controls.accountType.value !== this.accountType) {
      this.form.controls.accountType.setValue(this.accountType);
    }
    if (this.status() !== 'matched' && !(this.status() === 'mismatch' && this.proof)) {
      this.error.set('Complete penny drop, or upload bank proof after a mismatch.');
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
