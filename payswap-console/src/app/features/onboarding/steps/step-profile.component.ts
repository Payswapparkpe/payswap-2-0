import { Component, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatRadioModule } from '@angular/material/radio';
import { MatSelectModule } from '@angular/material/select';
import { BUSINESS_CATEGORIES, MONTHLY_VOLUMES } from '../../../core/config/business-categories';
import { ENTITY_LABELS, EntityType, KycApplication, UdyamDetails } from '../../../core/models/onboarding.models';
import { nextOnboardingStep, prevOnboardingStep, onboardingNav, rulesFor } from '../../../core/config/entity-rules';
import { VerificationService } from '../../../core/services/verification.service';
import { namesClearlyDiffer } from '../../../core/utils/feedback.util';
import { isVerificationLocked, registryCheckVerified } from '../../../core/utils/verification-lock.util';

@Component({
  selector: 'app-step-profile',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule,
    MatRadioModule,
    MatSelectModule,
  ],
  template: `
    <form [formGroup]="form" (ngSubmit)="next()">
      @if (application.signatory.verified) {
        <p class="lede">Person KYC is done. Entity type is set — complete the remaining business details.</p>
      } @else {
        <p class="lede">Choose your entity type and trade name. Use Back if you still need to complete person KYC.</p>
      }
      <div class="grid">
        <mat-form-field appearance="outline">
          <mat-label>Entity type</mat-label>
          <mat-select formControlName="entityType">
            @for (item of entities; track item.id) {
              <mat-option [value]="item.id">{{ item.label }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ light() ? 'Display / trade name' : 'Brand / trade name' }}</mat-label>
          <input matInput formControlName="brandName" />
        </mat-form-field>
        @if (!light()) {
          <mat-form-field appearance="outline">
            <mat-label>Legal name (entity name)</mat-label>
            <input matInput formControlName="legalName" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Business category</mat-label>
            <mat-select formControlName="category">
              @for (cat of categories; track cat.id) {
                <mat-option [value]="cat.id">{{ cat.label }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Expected monthly volume</mat-label>
            <mat-select formControlName="monthlyVolume">
              @for (vol of volumes; track vol.id) {
                <mat-option [value]="vol.id">{{ vol.label }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Website or app URL</mat-label>
            <input matInput formControlName="website" placeholder="https://" />
          </mat-form-field>
        }
      </div>

      @if (needsUdyam()) {
        <div class="udyam">
          <div class="udyam-head">
            <h4>Udyam registration</h4>
            @if (udyamLocked()) {
              <span class="status-pill ok">Verified</span>
            }
          </div>
          @if (udyamLocked()) {
            <p class="ok">Udyam verified — details applied from MSME registry.</p>
            <div class="locked-field wide">
              <span class="lbl">Udyam number</span>
              <span class="val mono">{{ form.controls.udyamNumber.value }}</span>
            </div>
            @if (udyamDetails(); as details) {
              <dl class="udyam-meta">
                <div><dt>Enterprise</dt><dd>{{ details.enterpriseName }}</dd></div>
                <div><dt>Owner</dt><dd>{{ details.ownerName || application.signatory.name || '—' }}</dd></div>
                @if (details.enterpriseType) {
                  <div><dt>Classification</dt><dd>{{ details.enterpriseType }}</dd></div>
                }
                @if (details.majorActivity) {
                  <div><dt>Activity</dt><dd>{{ details.majorActivity }}</dd></div>
                }
                @if (details.address?.line1) {
                  <div class="wide"><dt>Registered address</dt><dd>{{ formatAddress(details.address!) }}</dd></div>
                }
              </dl>
            }
            @if (udyamWarning()) {
              <p class="warn">{{ udyamWarning() }}</p>
            }
          } @else {
            <p class="lede">Verify your Udyam Aadhaar (MSME) registration linked to this individual business.</p>
            <mat-form-field appearance="outline" class="wide">
              <mat-label>Udyam registration number</mat-label>
              <input matInput formControlName="udyamNumber" placeholder="UDYAM-XX-00-0000000" />
            </mat-form-field>
            @if (udyamError()) {
              <p class="warn">{{ udyamError() }}</p>
            }
            <button mat-stroked-button type="button" (click)="verifyUdyam()" [disabled]="udyamBusy()">
              {{ udyamBusy() ? 'Verifying…' : 'Verify Udyam' }}
            </button>
          }
        </div>
      }

      @if (canDiffer()) {
        <div class="owner">
          <p>
            Companies, LLPs, and similar entities appoint an authorised signatory by board resolution.
            Confirm whether you also hold ownership or a directorship, or you are acting only as the
            authorised signatory.
          </p>
          <mat-radio-group formControlName="signatoryIsOwner">
            <mat-radio-button [value]="true">I am a director, partner, or owner, and the authorised signatory</mat-radio-button>
            <mat-radio-button [value]="false">I am only the authorised signatory — owner KYC will be collected next</mat-radio-button>
          </mat-radio-group>
          @if (form.controls.signatoryIsOwner.value === true) {
            <p class="note">
              A certified board resolution (or letter of authority) is still required. The board
              appoints the authorised signatory even when that person is also a director or shareholder.
            </p>
          }
          @if (form.controls.signatoryIsOwner.value === false) {
            <p class="note">
              You will complete owner/director DigiLocker KYC next. On KYB, that verification auto-maps to the
              matching MCA director. You still need KYC for any other directors (minimum 2 for companies).
            </p>
          }
        </div>
      }

      <div class="actions">
        <button mat-button type="button" (click)="back()">Back</button>
        <button mat-flat-button color="primary" type="submit">Save and continue</button>
      </div>
    </form>
  `,
  styles: [
    `
      .lede,
      .owner p {
        color: #6d6484;
      }
      .note {
        margin: 12px 0 0;
        font-size: 13px;
        color: #3d3554;
      }
      .grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 4px 16px;
      }
      .wide {
        grid-column: 1 / -1;
      }
      .owner {
        margin: 16px 0 8px;
        padding: 14px;
        border-radius: 14px;
        background: #f7f4ff;
      }
      .udyam {
        margin: 16px 0;
        padding: 14px;
        border-radius: 14px;
        background: #f4f8ff;
        display: grid;
        gap: 10px;
      }
      .udyam h4 {
        margin: 0;
      }
      .udyam-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }
      .status-pill {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        padding: 4px 10px;
        border-radius: 999px;
        background: #e8f7ee;
        color: #0f7a3d;
      }
      .locked-field {
        display: grid;
        gap: 4px;
      }
      .locked-field.wide {
        grid-column: 1 / -1;
      }
      .locked-field .lbl {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #6d6484;
      }
      .locked-field .val {
        font-weight: 650;
        color: #2a223d;
      }
      .mono {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      }
      .ok {
        color: #0f7a3d;
        font-weight: 650;
        margin: 0;
      }
      .warn {
        color: #9a4b00;
        margin: 0;
        font-size: 13px;
      }
      .udyam-meta {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px 16px;
        margin: 0;
      }
      .udyam-meta div {
        margin: 0;
      }
      .udyam-meta dt {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #6d6484;
        margin: 0;
      }
      .udyam-meta dd {
        margin: 2px 0 0;
        font-weight: 600;
        color: #2a223d;
      }
      .udyam-meta .wide {
        grid-column: 1 / -1;
      }
      mat-radio-group {
        display: grid;
        gap: 8px;
      }
      .actions {
        display: flex;
        justify-content: space-between;
        margin-top: 12px;
      }
      @media (max-width: 720px) {
        .grid {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class StepProfileComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly verification = inject(VerificationService);
  @Input({ required: true }) application!: KycApplication;
  @Input() readonly = false;
  @Output() save = new EventEmitter<KycApplication>();

  readonly categories = BUSINESS_CATEGORIES;
  readonly volumes = MONTHLY_VOLUMES;
  readonly entities = (Object.keys(ENTITY_LABELS) as EntityType[]).map((id) => ({
    id,
    label: ENTITY_LABELS[id],
  }));

  readonly udyamBusy = signal(false);
  readonly udyamVerified = signal(false);
  readonly udyamError = signal('');
  readonly udyamWarning = signal('');
  readonly udyamDetails = signal<UdyamDetails | null>(null);

  private udyamCheck: KycApplication['identity']['udyamCheck'] = null;
  private udyamRegisteredAddress: KycApplication['identity']['registeredAddress'] | undefined;

  readonly form = this.fb.nonNullable.group({
    brandName: ['', Validators.required],
    legalName: [''],
    entityType: ['' as EntityType | '', Validators.required],
    category: [''],
    website: [''],
    monthlyVolume: [''],
    signatoryIsOwner: [null as boolean | null],
    udyamNumber: [''],
  });

  light(): boolean {
    return !!rulesFor(this.form.controls.entityType.value)?.lightProfile;
  }

  canDiffer(): boolean {
    return !!rulesFor(this.form.controls.entityType.value)?.canSignatoryDifferFromOwner;
  }

  needsUdyam(): boolean {
    return !!rulesFor(this.form.controls.entityType.value)?.needsUdyam;
  }

  udyamLocked(): boolean {
    return isVerificationLocked(this.udyamVerified(), this.application, 'profile');
  }

  ngOnInit(): void {
    this.form.patchValue({
      ...this.application.profile,
      signatoryIsOwner: this.application.signatoryIsOwner,
      legalName: this.application.profile.legalName || this.registryLegalName(),
      brandName: this.application.profile.brandName || this.registryLegalName(),
      udyamNumber: this.application.identity.udyamNumber || '',
    });
    this.udyamVerified.set(registryCheckVerified(this.application.identity.udyamCheck));
    const storedDetails = this.application.identity.udyamDetails ?? null;
    if (storedDetails && !storedDetails.ownerName && this.application.signatory.name) {
      this.udyamDetails.set({
        ...storedDetails,
        ownerName: storedDetails.enterpriseName || this.application.signatory.name,
      });
    } else {
      this.udyamDetails.set(storedDetails);
    }
    this.udyamCheck = this.application.identity.udyamCheck ?? null;
    this.udyamRegisteredAddress = this.application.identity.registeredAddress;
    this.syncUdyamFieldLock();
    this.form.controls.entityType.valueChanges.subscribe((type) => {
      const rules = rulesFor(type);
      if (!rules?.canSignatoryDifferFromOwner) {
        this.form.controls.signatoryIsOwner.setValue(true);
      } else if (this.form.controls.signatoryIsOwner.value === true && this.application.signatoryIsOwner == null) {
        this.form.controls.signatoryIsOwner.setValue(null);
      }
      this.applyValidators(type);
    });
    this.applyValidators(this.form.controls.entityType.value);
    if (this.readonly) {
      this.form.disable({ emitEvent: false });
    }
  }

  verifyUdyam(): void {
    const number = this.form.controls.udyamNumber.value.trim().toUpperCase();
    if (!number) {
      this.udyamError.set('Enter your Udyam registration number.');
      return;
    }
    this.form.controls.udyamNumber.setValue(number);
    this.udyamBusy.set(true);
    this.udyamError.set('');
    this.udyamWarning.set('');
    const ownerName = this.application.signatory.name || this.application.profile.legalName || '';
    this.verification.verifyUdyam(number, ownerName).subscribe({
      next: (result) => {
        this.udyamBusy.set(false);
        if (!result.valid) {
          this.udyamVerified.set(false);
          this.udyamError.set('Udyam verification failed. Check the number and try again.');
          return;
        }
        this.udyamVerified.set(true);
        this.udyamCheck = {
          verificationId: result.verificationId,
          referenceId: result.referenceId,
          status: 'VALID',
          registeredName: result.enterpriseName,
        };
        const resolvedOwner = result.ownerName || ownerName || result.enterpriseName;
        const details: UdyamDetails = {
          enterpriseName: result.enterpriseName,
          ownerName: resolvedOwner,
          organizationType: result.organizationType,
          enterpriseType: result.enterpriseType,
          majorActivity: result.majorActivity,
          dateOfUdyamRegistration: result.dateOfUdyamRegistration,
          dateOfIncorporation: result.dateOfIncorporation,
          dateOfCommencement: result.dateOfCommencement,
          address: result.address,
          nicCodes: result.nicCodes,
        };
        this.udyamDetails.set(details);
        if (result.address) {
          this.udyamRegisteredAddress = result.address;
        }
        if (result.enterpriseName) {
          this.form.controls.brandName.setValue(result.enterpriseName);
          if (!this.light()) {
            this.form.controls.legalName.setValue(result.enterpriseName);
          }
        }
        if (result.ownerNameMatchWarning || (ownerName && namesClearlyDiffer(resolvedOwner, ownerName))) {
          this.udyamWarning.set(
            `Registry owner "${resolvedOwner}" differs from signatory "${ownerName}". Confirm this Udyam belongs to the account opener.`,
          );
        }
        this.syncUdyamFieldLock();
      },
      error: (err: Error) => {
        this.udyamBusy.set(false);
        this.udyamVerified.set(false);
        this.udyamError.set(err.message || 'Udyam verification failed.');
      },
    });
  }

  formatAddress(address: { line1: string; line2?: string; city: string; state: string; pin: string }): string {
    return [address.line1, address.line2, address.city, address.state, address.pin].filter(Boolean).join(', ');
  }

  private syncUdyamFieldLock(): void {
    if (this.udyamLocked()) {
      this.form.controls.udyamNumber.disable({ emitEvent: false });
      return;
    }
    if (!this.readonly) {
      this.form.controls.udyamNumber.enable({ emitEvent: false });
    }
  }

  back(): void {
    this.save.emit({
      ...this.payload(),
      currentStep: onboardingNav(this.application).prev('profile'),
    });
  }

  next(): void {
    this.applyValidators(this.form.controls.entityType.value);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const type = this.form.controls.entityType.value;
    const rules = rulesFor(type);
    if (rules?.canSignatoryDifferFromOwner && this.form.controls.signatoryIsOwner.value === null) {
      this.form.controls.signatoryIsOwner.markAsTouched();
      this.form.controls.signatoryIsOwner.setErrors({ required: true });
      return;
    }
    if (rules?.needsUdyam && !this.udyamVerified()) {
      this.udyamError.set('Verify Udyam registration before continuing.');
      return;
    }
    const nextApp = this.payload();
    this.save.emit({
      ...nextApp,
      currentStep: onboardingNav(nextApp).next('profile'),
    });
  }

  private applyValidators(type: EntityType | ''): void {
    const rules = rulesFor(type);
    const legal = this.form.controls.legalName;
    const category = this.form.controls.category;
    const volume = this.form.controls.monthlyVolume;
    if (rules && !rules.lightProfile) {
      legal.setValidators([Validators.required]);
      category.setValidators([Validators.required]);
      volume.setValidators([Validators.required]);
    } else {
      legal.clearValidators();
      category.clearValidators();
      volume.clearValidators();
    }
    legal.updateValueAndValidity({ emitEvent: false });
    category.updateValueAndValidity({ emitEvent: false });
    volume.updateValueAndValidity({ emitEvent: false });
  }

  private payload(): KycApplication {
    const value = this.form.getRawValue();
    const rules = rulesFor(value.entityType);
    const legalName = rules?.lightProfile ? value.brandName : value.legalName || this.registryLegalName();
    const signatoryIsOwner = rules?.canSignatoryDifferFromOwner ? value.signatoryIsOwner : true;
    return {
      ...this.application,
      signatoryIsOwner,
      identity: {
        ...this.application.identity,
        udyamNumber: value.udyamNumber,
        udyamCheck: this.udyamVerified() ? this.udyamCheck : this.application.identity.udyamCheck ?? null,
        udyamDetails: this.udyamVerified() ? this.udyamDetails() : this.application.identity.udyamDetails ?? null,
        registeredAddress: this.udyamRegisteredAddress || this.application.identity.registeredAddress,
        operatingAddress: this.udyamRegisteredAddress || this.application.identity.operatingAddress,
      },
      profile: {
        brandName: value.brandName || legalName,
        legalName,
        entityType: value.entityType,
        category: value.category,
        subCategory: '',
        website: value.website,
        monthlyVolume: value.monthlyVolume,
        gstin: this.application.profile.gstin,
        noGstin: this.application.profile.noGstin,
        gstinOptions: this.application.profile.gstinOptions ?? [],
      },
    };
  }

  private registryLegalName(): string {
    const identity = this.application.identity;
    return (
      this.application.profile.legalName ||
      identity.panCheck?.registeredName ||
      identity.gstinCheck?.registeredName ||
      identity.cinCheck?.registeredName ||
      identity.udyamCheck?.registeredName ||
      this.application.registryDirectors?.[0]?.name ||
      ''
    );
  }
}
