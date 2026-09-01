import { Component, EventEmitter, Input, OnInit, Output, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatRadioModule } from '@angular/material/radio';
import { MatSelectModule } from '@angular/material/select';
import { BUSINESS_CATEGORIES, MONTHLY_VOLUMES } from '../../../core/config/business-categories';
import { ENTITY_LABELS, EntityType, KycApplication } from '../../../core/models/onboarding.models';
import { nextOnboardingStep, prevOnboardingStep, rulesFor } from '../../../core/config/entity-rules';

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
      <p class="lede">Person KYC is done. Entity type is set — complete the remaining business details.</p>
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
              You will verify a business owner’s identity (DigiLocker and physical documents) before
              entity KYB. Beneficial owners above the control threshold are listed separately.
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
  @Input({ required: true }) application!: KycApplication;
  @Output() save = new EventEmitter<KycApplication>();

  readonly categories = BUSINESS_CATEGORIES;
  readonly volumes = MONTHLY_VOLUMES;
  readonly entities = (Object.keys(ENTITY_LABELS) as EntityType[]).map((id) => ({
    id,
    label: ENTITY_LABELS[id],
  }));

  readonly form = this.fb.nonNullable.group({
    brandName: ['', Validators.required],
    legalName: [''],
    entityType: ['' as EntityType | '', Validators.required],
    category: [''],
    website: [''],
    monthlyVolume: [''],
    signatoryIsOwner: [null as boolean | null],
  });

  light(): boolean {
    return !!rulesFor(this.form.controls.entityType.value)?.lightProfile;
  }

  canDiffer(): boolean {
    return !!rulesFor(this.form.controls.entityType.value)?.canSignatoryDifferFromOwner;
  }

  ngOnInit(): void {
    this.form.patchValue({
      ...this.application.profile,
      signatoryIsOwner: this.application.signatoryIsOwner,
    });
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
  }

  back(): void {
    this.save.emit({
      ...this.payload(),
      currentStep: prevOnboardingStep('profile', this.form.controls.entityType.value, this.form.controls.signatoryIsOwner.value),
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
    const next = this.payload();
    this.save.emit({
      ...next,
      currentStep: nextOnboardingStep('profile', type, next.signatoryIsOwner),
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
    const legalName = rules?.lightProfile ? value.brandName : value.legalName;
    const signatoryIsOwner = rules?.canSignatoryDifferFromOwner ? value.signatoryIsOwner : true;
    return {
      ...this.application,
      signatoryIsOwner,
      profile: {
        brandName: value.brandName,
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
}
