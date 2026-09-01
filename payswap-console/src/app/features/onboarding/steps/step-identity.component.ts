import { Component, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { INDIAN_STATES } from '../../../core/config/indian-states';
import { kybPhysicalDocuments } from '../../../core/config/entity-documents';
import { ENTITY_LABELS, EntityType, GstinOption, KycApplication, panEntityHint, RegistryCheck, UploadedDoc } from '../../../core/models/onboarding.models';
import { pan, pinCode } from '../../../core/validators/india.validators';
import { FileDropzoneComponent } from '../../../shared/ui/file-dropzone/file-dropzone.component';
import { nextOnboardingStep, prevOnboardingStep, rulesFor } from '../../../core/config/entity-rules';
import { VerificationService } from '../../../core/services/verification.service';

@Component({
  selector: 'app-step-identity',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    FileDropzoneComponent,
  ],
  template: `
    <form [formGroup]="form" (ngSubmit)="next()">
      <p class="lede">
        Confirm the entity type, then complete registry KYB. Company PAN is required only for
        private limited, public limited, and partnership firms. GSTIN is fetched from PAN.
      </p>
      <mat-form-field appearance="outline" class="full">
        <mat-label>Entity type</mat-label>
        <mat-select formControlName="entityType">
          @for (item of entities; track item.id) {
            <mat-option [value]="item.id">{{ item.label }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      @if (rules()?.needsBusinessPan) {
      <div class="row">
        <mat-form-field appearance="outline">
          <mat-label>{{ rules()?.businessPanLabel || 'Business PAN' }}</mat-label>
          <input matInput formControlName="pan" />
        </mat-form-field>
        <button mat-stroked-button type="button" (click)="verifyPan()" [disabled]="panBusy()">
          {{ panBusy() ? 'Verifying…' : panCheck?.status === 'VALID' ? 'PAN verified' : 'Verify PAN' }}
        </button>
      </div>
      }
      @if (hint()) {
        <p class="hint">PAN fourth character suggests {{ hint() }}. Confirm this matches the entity you selected.</p>
      }
      <div class="grid">
        @if (rules()?.needsDoi) {
        <mat-form-field appearance="outline">
          <mat-label>Date of incorporation</mat-label>
          <input matInput type="date" formControlName="doi" />
        </mat-form-field>
        }
        @if (rules()?.needsCin) {
        <div class="row wide-row">
          <mat-form-field appearance="outline">
            <mat-label>CIN</mat-label>
            <input matInput formControlName="cin" />
          </mat-form-field>
          <button mat-stroked-button type="button" (click)="verifyCin()" [disabled]="cinBusy()">
            {{ cinBusy() ? 'Verifying…' : cinCheck?.status === 'VALID' ? 'CIN verified' : 'Verify CIN' }}
          </button>
        </div>
        }
        @if (rules()?.needsLlpin) {
        <mat-form-field appearance="outline">
          <mat-label>LLPIN</mat-label>
          <input matInput formControlName="llpin" />
        </mat-form-field>
        }
      </div>

      <h4>Registered office</h4>
      <div class="grid" formGroupName="registeredAddress">
        <mat-form-field appearance="outline" class="wide">
          <mat-label>Address line 1</mat-label>
          <input matInput formControlName="line1" />
        </mat-form-field>
        <mat-form-field appearance="outline" class="wide">
          <mat-label>Address line 2</mat-label>
          <input matInput formControlName="line2" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>City</mat-label>
          <input matInput formControlName="city" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>State</mat-label>
          <mat-select formControlName="state">
            @for (state of states; track state) {
              <mat-option [value]="state">{{ state }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>PIN code</mat-label>
          <input matInput formControlName="pin" maxlength="6" />
        </mat-form-field>
      </div>

      <mat-checkbox formControlName="sameAsRegistered">Principal place of business is the same</mat-checkbox>

      @if (!form.controls.sameAsRegistered.value) {
        <h4>Principal place of business</h4>
        <div class="grid" formGroupName="operatingAddress">
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Address line 1</mat-label>
            <input matInput formControlName="line1" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>City</mat-label>
            <input matInput formControlName="city" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>State</mat-label>
            <mat-select formControlName="state">
              @for (state of states; track state) {
                <mat-option [value]="state">{{ state }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>PIN code</mat-label>
            <input matInput formControlName="pin" />
          </mat-form-field>
        </div>
      }

      @if (showGst()) {
        <div class="gst-box">
          <h4>GSTIN (fetched from PAN)</h4>
          <p class="lede">
            GST registrations linked to this PAN are fetched automatically. If GSTIN was not provided,
            select from the list or confirm that this entity is not registered.
          </p>
          <div class="row">
            <button mat-stroked-button type="button" (click)="fetchGstins()" [disabled]="gstBusy() || !panForGst()">
              {{ gstBusy() ? 'Fetching…' : gstOptions.length ? 'Refresh GST list' : 'Fetch GSTINs for this PAN' }}
            </button>
          </div>
          @if (gstOptions.length) {
            <mat-form-field appearance="outline" class="full">
              <mat-label>GSTIN on this PAN</mat-label>
              <mat-select formControlName="gstin" (selectionChange)="onGstinPicked()">
                <mat-option value="">Select GSTIN</mat-option>
                @for (opt of gstOptions; track opt.gstin) {
                  <mat-option [value]="opt.gstin">{{ opt.gstin }} · {{ opt.state }} · {{ opt.status }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
          } @else if (gstLookedUp()) {
            <p class="hint">No GSTIN returned for this PAN. Confirm below if the entity is unregistered.</p>
          }
          <mat-checkbox formControlName="noGstin">This entity is not registered under GST</mat-checkbox>
          @if (form.controls.gstin.value && !form.controls.noGstin.value) {
            <button mat-stroked-button type="button" (click)="verifyGstin()" [disabled]="gstBusy()">
              {{ gstBusy() ? 'Verifying…' : gstinCheck?.status === 'VALID' ? 'GSTIN verified' : 'Verify GSTIN' }}
            </button>
          }
        </div>
      }

      @if (rules()?.needsAuthorisationInstrument) {
        <aside class="callout">
          <strong>Board resolution.</strong>
          Companies, LLPs, and similar entities must upload a certified board resolution (or letter of
          authority) appointing the authorised signatory. This is required even when the signatory is
          also a director, partner, or shareholder.
        </aside>
      }

      @if (kybSlots.length) {
        <h4>Physical business documents</h4>
        <p class="lede">Upload colour scans for this entity. Bank proof stays on the bank step.</p>
        @for (slot of kybSlots; track slot.id) {
          <app-file-dropzone
            [label]="slot.label + (slot.required ? '' : ' (optional)')"
            [hint]="slot.hint"
            [slotId]="slot.id"
            [accept]="slot.accept"
            [value]="doc(slot.id)"
            (valueChange)="setDoc(slot.id, $event)"
          />
        }
      }

      @if (error()) {
        <p class="error">{{ error() }}</p>
      }

      <div class="actions">
        <button mat-button type="button" (click)="back()">Back</button>
        <button mat-flat-button color="primary" type="submit">Save and continue</button>
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
      .wide {
        grid-column: 1 / -1;
      }
      .full {
        width: 100%;
      }
      .gst-box {
        display: grid;
        gap: 10px;
        padding: 14px;
        border-radius: 14px;
        background: #f7f4ff;
        margin: 12px 0;
      }
      .row {
        display: flex;
        gap: 12px;
        align-items: flex-start;
      }
      .row mat-form-field {
        flex: 1;
      }
      .row button {
        margin-top: 8px;
      }
      .wide-row {
        display: flex;
        gap: 12px;
        align-items: flex-start;
        grid-column: 1 / -1;
      }
      .gst-line {
        margin: 12px 0 0;
        font-weight: 650;
      }
      .error {
        color: #b42318;
      }
      .hint {
        background: #eef3ff;
        color: #1b4dfe;
        padding: 10px 12px;
        border-radius: 10px;
      }
      .callout {
        background: #fff6e8;
        color: #6a3b00;
        padding: 12px 14px;
        border-radius: 12px;
        font-size: 13px;
        margin: 8px 0 16px;
        line-height: 1.45;
      }
      .actions {
        display: flex;
        justify-content: space-between;
        margin-top: 16px;
      }
      @media (max-width: 720px) {
        .grid,
        .row {
          grid-template-columns: 1fr;
          flex-direction: column;
        }
      }
    `,
  ],
})
export class StepIdentityComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly verification = inject(VerificationService);

  @Input({ required: true }) application!: KycApplication;
  @Output() save = new EventEmitter<KycApplication>();

  readonly states = INDIAN_STATES;
  readonly panBusy = signal(false);
  readonly gstBusy = signal(false);
  readonly cinBusy = signal(false);
  readonly hint = signal('');
  readonly error = signal('');
  readonly gstLookedUp = signal(false);
  panCheck: RegistryCheck | null = null;
  gstinCheck: RegistryCheck | null = null;
  cinCheck: RegistryCheck | null = null;
  kybDocs: UploadedDoc[] = [];
  gstOptions: GstinOption[] = [];

  readonly entities = (Object.keys(ENTITY_LABELS) as EntityType[]).map((id) => ({
    id,
    label: ENTITY_LABELS[id],
  }));

  readonly form = this.fb.nonNullable.group({
    entityType: ['' as EntityType | '', Validators.required],
    pan: [''],
    doi: [''],
    cin: [''],
    llpin: [''],
    gstin: [''],
    noGstin: [false],
    sameAsRegistered: [true],
    registeredAddress: this.fb.nonNullable.group({
      line1: ['', Validators.required],
      line2: [''],
      city: ['', Validators.required],
      state: ['', Validators.required],
      pin: ['', [Validators.required, pinCode()]],
    }),
    operatingAddress: this.fb.nonNullable.group({
      line1: [''],
      line2: [''],
      city: [''],
      state: [''],
      pin: [''],
    }),
  });

  rules() {
    return rulesFor(this.form.controls.entityType.value || this.application.profile.entityType);
  }

  showGst(): boolean {
    return this.rules()?.gst === 'optional';
  }

  panForGst(): string {
    return (this.form.controls.pan.value || this.application.signatory.pan || '').toUpperCase();
  }

  get kybSlots() {
    const gstinProvided = !!(this.application.profile.gstin && !this.application.profile.noGstin);
    return kybPhysicalDocuments(this.application.profile.entityType, this.application.profile.category, gstinProvided);
  }

  ngOnInit(): void {
    const identity = { ...this.application.identity };
    if (!identity.pan && this.application.signatory.pan && !this.rules()?.needsBusinessPan) {
      identity.pan = this.application.signatory.pan;
    }
    if (!identity.pan && this.application.signatory.pan && this.rules()?.bankMatches === 'person') {
      identity.pan = this.application.signatory.pan;
    }
    this.form.patchValue({
      ...identity,
      entityType: this.application.profile.entityType,
      gstin: this.application.profile.gstin,
      noGstin: this.application.profile.noGstin,
    });
    this.gstOptions = this.application.profile.gstinOptions ?? [];
    this.gstLookedUp.set(this.gstOptions.length > 0);
    this.panCheck = identity.panCheck ?? null;
    this.gstinCheck = identity.gstinCheck ?? null;
    this.cinCheck = identity.cinCheck ?? null;
    const kybIds = new Set(this.kybSlots.map((s) => s.id));
    this.kybDocs = this.application.documents.filter((d) => kybIds.has(d.slotId));
    const hinted = panEntityHint(this.form.controls.pan.value);
    if (hinted) {
      this.hint.set(ENTITY_LABELS[hinted]);
    }
    this.applyFieldValidators();
    if (this.showGst() && this.panForGst() && !this.gstLookedUp()) {
      this.fetchGstins();
    }
  }

  doc(slotId: string): UploadedDoc | undefined {
    return this.kybDocs.find((d) => d.slotId === slotId);
  }

  setDoc(slotId: string, file?: UploadedDoc): void {
    this.kybDocs = this.kybDocs.filter((d) => d.slotId !== slotId);
    if (file) {
      this.kybDocs.push({ ...file, slotId });
    }
  }

  verifyPan(): void {
    const panValue = this.form.controls.pan.value.toUpperCase();
    this.form.controls.pan.setValue(panValue);
    if (this.form.controls.pan.invalid) {
      this.form.controls.pan.markAsTouched();
      return;
    }
    this.panBusy.set(true);
    this.error.set('');
    this.verification.verifyPan(panValue).subscribe((result) => {
      this.panBusy.set(false);
      this.panCheck = {
        verificationId: result.verificationId,
        referenceId: result.referenceId,
        status: result.status,
        registeredName: result.registeredName,
      };
      if (result.status !== 'VALID') {
        this.error.set('PAN verification failed. Demo: avoid PAN ending in 0.');
        return;
      }
      const hinted = panEntityHint(panValue);
      this.hint.set(hinted ? ENTITY_LABELS[hinted] : result.panType);
      if (result.registeredName && !this.application.profile.legalName) {
        this.application = {
          ...this.application,
          profile: { ...this.application.profile, legalName: result.registeredName },
        };
      }
      if (this.rules()?.needsDoi && !this.form.controls.doi.value) {
        this.form.controls.doi.setValue('2019-04-12');
      }
      this.fetchGstins();
    });
  }

  fetchGstins(): void {
    const panValue = this.panForGst();
    if (!panValue || panValue.length < 10) {
      this.error.set('Enter a PAN to fetch GSTINs.');
      return;
    }
    this.gstBusy.set(true);
    this.error.set('');
    this.verification.lookupGstinsByPan(panValue).subscribe((result) => {
      this.gstBusy.set(false);
      this.gstLookedUp.set(true);
      this.gstOptions = result.gstins;
      if (!this.form.controls.gstin.value && result.gstins.length === 1) {
        this.form.controls.gstin.setValue(result.gstins[0].gstin);
        this.onGstinPicked();
      }
    });
  }

  onGstinPicked(): void {
    if (this.form.controls.gstin.value) {
      this.form.controls.noGstin.setValue(false);
      this.verifyGstin();
    }
  }

  verifyGstin(): void {
    const gstin = this.form.controls.gstin.value;
    if (!gstin) {
      return;
    }
    this.gstBusy.set(true);
    this.error.set('');
    this.verification.verifyGstin(gstin).subscribe((result) => {
      this.gstBusy.set(false);
      this.gstinCheck = {
        verificationId: result.verificationId,
        referenceId: result.referenceId,
        status: result.valid ? 'VALID' : 'INVALID',
        registeredName: result.legalName,
      };
      if (!result.valid) {
        this.error.set('GSTIN verification failed. Demo: avoid GSTIN ending in 0.');
      }
    });
  }

  verifyCin(): void {
    const cin = this.form.controls.cin.value.toUpperCase();
    this.form.controls.cin.setValue(cin);
    if (!cin) {
      this.form.controls.cin.markAsTouched();
      return;
    }
    this.cinBusy.set(true);
    this.error.set('');
    this.verification.verifyCin(cin).subscribe((result) => {
      this.cinBusy.set(false);
      this.cinCheck = {
        verificationId: result.verificationId,
        referenceId: result.referenceId,
        status: result.status,
        registeredName: result.companyName,
      };
      if (result.status !== 'VALID') {
        this.error.set('CIN verification failed. Demo: avoid CIN ending in 0.');
        return;
      }
      if (result.dateOfIncorporation) {
        this.form.controls.doi.setValue(result.dateOfIncorporation);
      }
    });
  }

  back(): void {
    this.save.emit({
      ...this.withIdentity(),
      currentStep: prevOnboardingStep('identity', this.form.controls.entityType.value, this.application.signatoryIsOwner),
    });
  }

  next(): void {
    this.applyFieldValidators();
    this.error.set('');
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    if (this.rules()?.needsBusinessPan && this.panCheck?.status !== 'VALID') {
      this.error.set('Verify the business PAN before continuing.');
      return;
    }
    if (this.rules()?.needsCin && this.cinCheck?.status !== 'VALID') {
      this.error.set('Verify the CIN before continuing.');
      return;
    }
    if (this.form.controls.gstin.value && !this.form.controls.noGstin.value && this.gstinCheck?.status !== 'VALID') {
      this.error.set('Verify the GSTIN before continuing.');
      return;
    }
    if (this.showGst() && !this.form.controls.noGstin.value && !this.form.controls.gstin.value) {
      if (!this.gstLookedUp()) {
        this.fetchGstins();
        this.error.set('Fetch GSTINs for this PAN, or confirm that the entity is not registered under GST.');
        return;
      }
      this.error.set('Select a GSTIN from the PAN list, or confirm that the entity is not registered under GST.');
      return;
    }
    const missing = this.kybSlots.filter((s) => s.required && !this.doc(s.id));
    if (missing.length) {
      this.error.set(`Upload: ${missing.map((s) => s.label).join(', ')}`);
      return;
    }
    this.save.emit({
      ...this.withIdentity(),
      currentStep: nextOnboardingStep('identity', this.form.controls.entityType.value, this.application.signatoryIsOwner),
    });
  }

  private applyFieldValidators(): void {
    const rules = this.rules();
    const panCtrl = this.form.controls.pan;
    const doi = this.form.controls.doi;
    const cin = this.form.controls.cin;
    const llpin = this.form.controls.llpin;
    panCtrl.setValidators(rules?.needsBusinessPan ? [Validators.required, pan()] : []);
    doi.setValidators(rules?.needsDoi ? [Validators.required] : []);
    cin.setValidators(rules?.needsCin ? [Validators.required] : []);
    llpin.setValidators(rules?.needsLlpin ? [Validators.required] : []);
    panCtrl.updateValueAndValidity({ emitEvent: false });
    doi.updateValueAndValidity({ emitEvent: false });
    cin.updateValueAndValidity({ emitEvent: false });
    llpin.updateValueAndValidity({ emitEvent: false });
  }

  private withIdentity(): KycApplication {
    const raw = this.form.getRawValue();
    const keep = this.application.documents.filter((d) => !this.kybSlots.some((s) => s.id === d.slotId));
    const noGstin = this.showGst() ? raw.noGstin : true;
    return {
      ...this.application,
      profile: {
        ...this.application.profile,
        entityType: raw.entityType,
        gstin: noGstin ? '' : raw.gstin,
        noGstin,
        gstinOptions: this.gstOptions,
      },
      identity: {
        pan: raw.pan,
        doi: raw.doi,
        cin: raw.cin,
        llpin: raw.llpin,
        sameAsRegistered: raw.sameAsRegistered,
        registeredAddress: raw.registeredAddress,
        operatingAddress: raw.operatingAddress,
        panCheck: this.panCheck,
        gstinCheck: this.gstinCheck,
        cinCheck: this.cinCheck,
      },
      documents: [...keep, ...this.kybDocs],
    };
  }
}
