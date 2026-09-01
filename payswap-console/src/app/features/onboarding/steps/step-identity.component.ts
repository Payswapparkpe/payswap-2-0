import { Component, ElementRef, EventEmitter, Input, OnInit, Output, ViewChild, inject, signal } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { INDIAN_STATES } from '../../../core/config/indian-states';
import { kybPhysicalDocuments } from '../../../core/config/entity-documents';
import { directorKycLinkedFrom, syncDirectorsFromApplication } from '../../../core/config/person-kyc-link.util';
import {
  Address,
  ENTITY_LABELS,
  EntityType,
  GstinOption,
  KycApplication,
  panEntityHint,
  RegistryCheck,
  RegistryDirector,
  UploadedDoc,
} from '../../../core/models/onboarding.models';
import { MOBILE_PATTERN, PAN_PATTERN, pan, pinCode } from '../../../core/validators/india.validators';
import { FileDropzoneComponent } from '../../../shared/ui/file-dropzone/file-dropzone.component';
import { InlineAlertComponent } from '../../../shared/ui/inline-alert/inline-alert.component';
import { nextOnboardingStep, prevOnboardingStep, onboardingNav, rulesFor } from '../../../core/config/entity-rules';
import { scrollToFeedback, namesClearlyDiffer } from '../../../core/utils/feedback.util';
import { isVerificationLocked, registryCheckVerified } from '../../../core/utils/verification-lock.util';
import {
  CinVerifyResult,
  DigilockerStatusResult,
  GstinVerifyResult,
  PanVerifyResult,
  VerificationService,
} from '../../../core/services/verification.service';
import { DigilockerSessionService } from '../../../core/services/digilocker-session.service';
import { PartnerRegistryBlockComponent } from '../blocks/partner-registry-block.component';

@Component({
  selector: 'app-step-identity',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    FormsModule,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    FileDropzoneComponent,
    InlineAlertComponent,
    PartnerRegistryBlockComponent,
  ],
  template: `
    <form [formGroup]="form" (ngSubmit)="next()" class="kyb-form">
      <header class="step-header">
        <h3>Entity KYB</h3>
        <p>Verify registry records in order — PAN, CIN, then GSTIN. Verified fields lock automatically.</p>
      </header>

      <section class="card">
        <div class="card-head">
          <span class="step-badge">1</span>
          <div>
            <h4>Entity type</h4>
            <p class="card-sub">Must match the PAN fourth character.</p>
          </div>
        </div>
        <mat-form-field appearance="outline" class="full">
          <mat-label>Entity type</mat-label>
          <mat-select formControlName="entityType">
            @for (item of entities; track item.id) {
              <mat-option [value]="item.id">{{ item.label }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </section>

      @if (rules()?.needsBusinessPan) {
        <section class="card">
          <div class="card-head">
            <span class="step-badge">2</span>
            <div>
              <h4>PAN 360 verification</h4>
              <p class="card-sub">Legal name, incorporation date, and contact from Income Tax.</p>
            </div>
            @if (panLocked()) {
              <span class="status-pill ok">Verified</span>
            }
          </div>

          @if (!panLocked()) {
            <div class="row">
              <mat-form-field appearance="outline">
                <mat-label>{{ rules()?.businessPanLabel || 'Business PAN' }}</mat-label>
                <input matInput formControlName="pan" class="mono" />
              </mat-form-field>
              <button mat-flat-button color="primary" type="button" (click)="verifyPan()" [disabled]="panBusy()">
                {{ panBusy() ? 'Verifying…' : 'Verify PAN' }}
              </button>
            </div>
            @if (hint()) {
              <p class="hint">PAN suggests {{ hint() }} — confirm entity type above.</p>
            }
            @if (panAlert()) {
              <app-inline-alert [message]="panAlert()" tone="error" />
            }
            @if (panWarning()) {
              <app-inline-alert [message]="panWarning()" tone="info" />
            }
          } @else {
            <div class="locked-grid">
              <div class="locked-field">
                <span class="lbl">Business PAN</span>
                <span class="val mono">{{ form.controls.pan.value }}</span>
              </div>
              <div class="locked-field wide">
                <span class="lbl">Legal name</span>
                <span class="val">{{ panDetails()?.registeredName }}</span>
              </div>
              <div class="locked-field">
                <span class="lbl">Entity type (ITD)</span>
                <span class="val">{{ panDetails()?.panType }}</span>
              </div>
              @if (panDetails()?.incorporationDate || panDetails()?.dateOfBirth) {
                <div class="locked-field">
                  <span class="lbl">Incorporation date</span>
                  <span class="val">{{ panDetails()?.incorporationDate || panDetails()?.dateOfBirth }}</span>
                </div>
              }
              @if (panDetails()?.email) {
                <div class="locked-field">
                  <span class="lbl">Email</span>
                  <span class="val">{{ panDetails()?.email }}</span>
                </div>
              }
              @if (panDetails()?.mobile) {
                <div class="locked-field">
                  <span class="lbl">Mobile</span>
                  <span class="val">{{ panDetails()?.mobile }}</span>
                </div>
              }
            </div>
          }
        </section>
      }

      @if (rules()?.needsCin) {
        <section class="card">
          <div class="card-head">
            <span class="step-badge">{{ rules()?.needsBusinessPan ? '3' : '2' }}</span>
            <div>
              <h4>CIN / MCA verification</h4>
              <p class="card-sub">Registered office and directors from Ministry of Corporate Affairs.</p>
            </div>
            @if (cinLocked()) {
              <span class="status-pill ok">Verified</span>
            }
          </div>

          @if (!cinLocked()) {
            <div class="row">
              <mat-form-field appearance="outline">
                <mat-label>CIN</mat-label>
                <input matInput formControlName="cin" class="mono" />
              </mat-form-field>
              <button mat-flat-button color="primary" type="button" (click)="verifyCin()" [disabled]="cinBusy()">
                {{ cinBusy() ? 'Verifying…' : 'Verify CIN' }}
              </button>
            </div>
            @if (cinAlert()) {
              <app-inline-alert [message]="cinAlert()" tone="error" />
            }
          } @else {
            <div class="locked-grid">
              <div class="locked-field wide">
                <span class="lbl">CIN</span>
                <span class="val mono">{{ form.controls.cin.value }}</span>
              </div>
              <div class="locked-field wide">
                <span class="lbl">Company name</span>
                <span class="val">{{ cinDetails()?.companyName }}</span>
              </div>
              <div class="locked-field">
                <span class="lbl">MCA status</span>
                <span class="val">{{ cinDetails()?.companyStatus }}</span>
              </div>
              <div class="locked-field">
                <span class="lbl">Incorporated</span>
                <span class="val">{{ cinDetails()?.dateOfIncorporation }}</span>
              </div>
              @if (cinDetails()?.companyEmail) {
                <div class="locked-field wide">
                  <span class="lbl">Company email</span>
                  <span class="val">{{ cinDetails()?.companyEmail }}</span>
                </div>
              }
            </div>
          }

          @if (cinLocked() && cinWarning()) {
            <app-inline-alert [message]="cinWarning()" tone="info" />
          }

          @if (cinLocked() && registryDirectors.length) {
            <div class="directors-block">
              <div class="directors-head">
                <h5>Director KYC</h5>
                <p>Verify at least {{ minDirectorKyc() }} directors from the MCA record using DigiLocker. Your own account KYC (and owner KYC, if collected) auto-maps when the name or PAN matches — only other directors need a separate verification.</p>
                <p class="digilocker-note">
                  DigiLocker opens in a secure popup (government sites cannot run inside iframe). Keep this
                  tab open — the panel closes automatically when OTP verification succeeds.
                </p>
              </div>
              @for (director of registryDirectors; track director.din || director.name) {
                <article class="director-card" [class.done]="director.kycVerified">
                  <div class="director-meta">
                    <strong>{{ director.name }}</strong>
                    <span>{{ director.designation }} · DIN {{ director.din }}</span>
                    @if (director.dob) {
                      <span>DOB {{ director.dob }}</span>
                    }
                  </div>
                  @if (director.kycVerified && directorKycLocked(director)) {
                    <div class="locked-grid compact">
                      @if (directorKycLinkedFrom(director); as linked) {
                        <p class="linked-note">
                          Verified from {{ linked === 'signatory' ? 'your account KYC (Step 1)' : 'owner KYC' }} — no repeat DigiLocker needed.
                        </p>
                      }
                      <div class="locked-field wide">
                        <span class="lbl">Verified name</span>
                        <span class="val">{{ director.name }}</span>
                      </div>
                      @if (directorKycDetails(director)?.dob) {
                        <div class="locked-field">
                          <span class="lbl">DOB</span>
                          <span class="val">{{ directorKycDetails(director)?.dob }}</span>
                        </div>
                      }
                      @if (directorKycDetails(director)?.mobile) {
                        <div class="locked-field">
                          <span class="lbl">Mobile</span>
                          <span class="val">{{ directorKycDetails(director)?.mobile }}</span>
                        </div>
                      }
                    </div>
                    <p class="ok-inline">KYC verified via DigiLocker</p>
                  } @else if (!readonly) {
                    <div class="director-kyc">
                      <mat-form-field appearance="outline">
                        <mat-label>Director PAN</mat-label>
                        <input matInput [(ngModel)]="director.pan" [ngModelOptions]="{ standalone: true }" class="mono" />
                      </mat-form-field>
                      <mat-form-field appearance="outline">
                        <mat-label>Mobile (DigiLocker)</mat-label>
                        <input matInput [(ngModel)]="director.mobile" [ngModelOptions]="{ standalone: true }" maxlength="10" />
                      </mat-form-field>
                      <mat-checkbox [(ngModel)]="director.digiConsent" [ngModelOptions]="{ standalone: true }">
                        Consent to fetch identity from DigiLocker
                      </mat-checkbox>
                      <button
                        mat-stroked-button
                        type="button"
                        (click)="verifyDirectorKyc(director)"
                        [disabled]="directorKycBusy() === directorKey(director)"
                      >
                        {{
                          directorKycBusy() === directorKey(director)
                            ? directorKycLabel()
                            : 'Verify director KYC'
                        }}
                      </button>
                      @if (director.digilocker?.verificationId) {
                        <button
                          mat-button
                          type="button"
                          (click)="refreshDirectorKyc(director)"
                          [disabled]="directorKycBusy() === directorKey(director)"
                        >
                          Refresh status
                        </button>
                      }
                    </div>
                  }
                </article>
              }
              <p class="progress-line">
                {{ verifiedDirectorCount() }} of {{ minDirectorKyc() }} required director KYC complete
              </p>
              @if (directorAlert()) {
                <app-inline-alert [message]="directorAlert()" tone="error" />
              }
            </div>
          }
        </section>
      }

      <section class="card">
        <div class="card-head">
          <span class="step-badge">{{ addressStepNumber() }}</span>
          <div>
            <h4>Registered office</h4>
            <p class="card-sub">Loaded from CIN / MCA record after verification.</p>
          </div>
          @if (addressLocked()) {
            <span class="status-pill ok">{{ rules()?.addressFromCin ? 'From CIN' : 'Confirmed' }}</span>
          }
        </div>

        @if (!addressLocked() && rules()?.addressFromCin) {
          <p class="wait-note">Verify CIN above to load and lock the registered office address.</p>
        }

        @if (!rules()?.addressFromCin) {
          <p class="wait-note">Enter the registered office address for this entity.</p>
        }

        <div class="grid" formGroupName="registeredAddress" [class.locked-block]="addressLocked()">
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

        @if (!form.controls.sameAsRegistered.value && addressLocked()) {
          <h5 class="sub-head">Principal place of business</h5>
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
      </section>

      @if (rules()?.needsPartnerRegistry) {
        <section class="card">
          <app-partner-registry-block
            [entityType]="registryEntityType()"
            [members]="registryMembers"
            [deedDoc]="registryDeedDoc"
            [readonly]="readonly"
            (membersChange)="onRegistryMembersChange($event)"
            (deedChange)="registryDeedDoc = $event"
          />
        </section>
      }

      @if (showGst()) {
        <section class="card gst-card">
          <div class="card-head">
            <span class="step-badge">{{ gstStepNumber() }}</span>
            <div>
              <h4>GSTIN</h4>
              <p class="card-sub">GST registrations linked to the verified business PAN.</p>
            </div>
            @if (gstLocked()) {
              <span class="status-pill ok">Verified</span>
            }
          </div>

          @if (!gstLocked()) {
            <div class="row">
              <button mat-stroked-button type="button" (click)="fetchGstins()" [disabled]="gstBusy() || !panForGst()">
                {{ gstBusy() ? 'Fetching…' : gstOptions.length ? 'Refresh GST list' : 'Fetch GSTINs for this PAN' }}
              </button>
            </div>
          }

          @if (gstOptions.length) {
            <mat-form-field appearance="outline" class="full">
              <mat-label>GSTIN on this PAN</mat-label>
              <mat-select formControlName="gstin" (selectionChange)="onGstinPicked()">
                @for (opt of gstOptions; track opt.gstin) {
                  <mat-option [value]="opt.gstin">{{ opt.gstin }} · {{ opt.state }} · {{ opt.status }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
          } @else if (gstLookedUp() && showNoGstinOption()) {
            <p class="hint">No GSTIN returned for this PAN.</p>
            <mat-checkbox formControlName="noGstin">This entity is not registered under GST</mat-checkbox>
          }

          @if (gstAlert()) {
            <app-inline-alert [message]="gstAlert()" tone="error" />
          }

          @if (gstLocked() && gstWarning()) {
            <app-inline-alert [message]="gstWarning()" tone="info" />
          }

          @if (gstLocked() && gstDetails()) {
            <div class="locked-grid">
              <div class="locked-field wide">
                <span class="lbl">GSTIN</span>
                <span class="val mono">{{ gstDetails()?.gstin }}</span>
              </div>
              <div class="locked-field wide">
                <span class="lbl">Legal name</span>
                <span class="val">{{ gstDetails()?.legalName }}</span>
              </div>
              <div class="locked-field">
                <span class="lbl">Status</span>
                <span class="val">{{ gstDetails()?.gstinStatus }}</span>
              </div>
              <div class="locked-field">
                <span class="lbl">Constitution</span>
                <span class="val">{{ gstDetails()?.constitutionOfBusiness }}</span>
              </div>
              @if (gstDetails()?.dateOfRegistration) {
                <div class="locked-field">
                  <span class="lbl">Registered</span>
                  <span class="val">{{ gstDetails()?.dateOfRegistration }}</span>
                </div>
              }
              @if (gstDetails()?.natureOfBusinessActivities?.length) {
                <div class="locked-field wide">
                  <span class="lbl">Activities</span>
                  <span class="val">{{ gstDetails()?.natureOfBusinessActivities?.join(', ') }}</span>
                </div>
              }
            </div>
          }
        </section>
      }

      @if (rules()?.needsLlpin) {
        <section class="card">
          <mat-form-field appearance="outline" class="full">
            <mat-label>LLPIN</mat-label>
            <input matInput formControlName="llpin" />
          </mat-form-field>
        </section>
      }

      @if (rules()?.needsAuthorisationInstrument) {
        <aside class="callout">
          <strong>Board resolution (BOR).</strong>
          Upload MOA, AOA, and a certified board resolution appointing the authorised signatory on this step.
        </aside>
      }

      @if (kybSlots.length) {
        <section class="card">
          <h4>Physical business documents</h4>
          <p class="card-sub">MOA, AOA, and board resolution (BOR) only. Person KYC is via DigiLocker; bank proof is on the bank step.</p>
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
        </section>
      }

      @if (submitError()) {
        <div #submitFeedback>
          <app-inline-alert [message]="submitError()" tone="error" />
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
      .kyb-form {
        display: grid;
        gap: 16px;
      }
      .step-header h3 {
        margin: 0 0 6px;
        font-size: 1.35rem;
        color: #2a2240;
      }
      .step-header p,
      .card-sub,
      .wait-note {
        margin: 0;
        color: #6d6484;
        font-size: 13px;
        line-height: 1.45;
      }
      .card {
        border: 1px solid #e8e2f4;
        border-radius: 16px;
        padding: 18px;
        background: linear-gradient(180deg, #ffffff 0%, #fbf9ff 100%);
        box-shadow: 0 8px 24px rgba(42, 34, 64, 0.05);
      }
      .gst-card {
        background: linear-gradient(180deg, #f8f5ff 0%, #f3eeff 100%);
      }
      .card-head {
        display: flex;
        gap: 12px;
        align-items: flex-start;
        margin-bottom: 14px;
      }
      .card-head h4,
      .directors-head h5,
      .sub-head {
        margin: 0 0 4px;
        color: #2a2240;
      }
      .digilocker-note {
        margin: 8px 0 0;
        font-size: 12px;
        color: #5f5675;
        line-height: 1.45;
      }
      .locked-grid.compact {
        margin-top: 8px;
        padding: 10px;
      }
      .card-head > div {
        flex: 1;
      }
      .step-badge {
        width: 28px;
        height: 28px;
        border-radius: 999px;
        display: grid;
        place-items: center;
        font-size: 12px;
        font-weight: 700;
        color: #fff;
        background: linear-gradient(135deg, #6b4cff, #1b4dfe);
        flex-shrink: 0;
      }
      .status-pill {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        padding: 5px 10px;
        border-radius: 999px;
        background: #eef9f0;
        color: #0f7a3d;
      }
      .status-pill.ok {
        background: #e8f7ee;
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
        white-space: nowrap;
      }
      .locked-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        padding: 14px;
        border-radius: 12px;
        background: #f4f1fb;
        border: 1px dashed #cfc4e8;
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
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: #7a7190;
      }
      .locked-field .val {
        font-size: 14px;
        color: #2a2240;
        word-break: break-word;
      }
      .mono {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        letter-spacing: 0.03em;
      }
      .locked-block {
        opacity: 0.92;
      }
      .directors-block {
        margin-top: 16px;
        display: grid;
        gap: 12px;
      }
      .director-card {
        border: 1px solid #e7e1f2;
        border-radius: 14px;
        padding: 14px;
        background: #fff;
      }
      .director-card.done {
        border-color: #b8e6c8;
        background: #f6fcf8;
      }
      .director-meta {
        display: grid;
        gap: 2px;
        margin-bottom: 10px;
        color: #5f5675;
        font-size: 13px;
      }
      .director-meta strong {
        color: #2a2240;
        font-size: 15px;
      }
      .director-kyc {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px 12px;
      }
      .director-kyc mat-checkbox,
      .director-kyc button {
        grid-column: 1 / -1;
      }
      .linked-note {
        margin: 0 0 8px;
        grid-column: 1 / -1;
        font-size: 12px;
        color: #0f7a3d;
        font-weight: 650;
      }
      .ok-inline {
        margin: 0;
        color: #0f7a3d;
        font-weight: 650;
        font-size: 13px;
      }
      .progress-line {
        margin: 0;
        font-size: 13px;
        color: #1b4dfe;
        font-weight: 650;
      }
      .error {
        color: #b42318;
        margin: 0;
      }
      .hint {
        background: #eef3ff;
        color: #1b4dfe;
        padding: 10px 12px;
        border-radius: 10px;
        font-size: 13px;
      }
      .callout {
        background: #fff6e8;
        color: #6a3b00;
        padding: 12px 14px;
        border-radius: 12px;
        font-size: 13px;
        line-height: 1.45;
      }
      .actions {
        display: flex;
        justify-content: space-between;
        margin-top: 4px;
      }
      @media (max-width: 720px) {
        .grid,
        .locked-grid,
        .director-kyc,
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
  private readonly digilockerSession = inject(DigilockerSessionService);

  @Input({ required: true }) application!: KycApplication;
  @Input() readonly = false;
  @Output() save = new EventEmitter<KycApplication>();

  @ViewChild('submitFeedback') submitFeedback?: ElementRef<HTMLElement>;

  readonly states = INDIAN_STATES;
  readonly panBusy = signal(false);
  readonly gstBusy = signal(false);
  readonly cinBusy = signal(false);
  readonly hint = signal('');
  readonly panAlert = signal('');
  readonly panWarning = signal('');
  readonly cinAlert = signal('');
  readonly cinWarning = signal('');
  readonly gstAlert = signal('');
  readonly gstWarning = signal('');
  readonly directorAlert = signal('');
  readonly submitError = signal('');
  readonly gstLookedUp = signal(false);
  readonly panDetails = signal<PanVerifyResult | null>(null);
  readonly gstDetails = signal<GstinVerifyResult | null>(null);
  readonly cinDetails = signal<CinVerifyResult | null>(null);
  readonly directorKycBusy = signal('');
  readonly directorKycLabel = signal('Connecting…');
  panCheck: RegistryCheck | null = null;
  gstinCheck: RegistryCheck | null = null;
  cinCheck: RegistryCheck | null = null;
  registryDirectors: RegistryDirector[] = [];
  registryMembers: RegistryDirector[] = [];
  registryDeedDoc?: UploadedDoc;
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

  panLocked(): boolean {
    return isVerificationLocked(registryCheckVerified(this.panCheck), this.application, 'identity');
  }

  cinLocked(): boolean {
    return isVerificationLocked(registryCheckVerified(this.cinCheck), this.application, 'identity');
  }

  addressLocked(): boolean {
    if (this.rules()?.addressFromCin) {
      return this.cinLocked();
    }
    const addr = this.form.controls.registeredAddress;
    return addr.valid && !!addr.controls.line1.value.trim();
  }

  gstLocked(): boolean {
    return isVerificationLocked(registryCheckVerified(this.gstinCheck), this.application, 'identity');
  }

  directorKycLocked(director: RegistryDirector): boolean {
    return isVerificationLocked(!!director.kycVerified, this.application, 'identity');
  }

  showGst(): boolean {
    return this.rules()?.gst === 'optional';
  }

  showNoGstinOption(): boolean {
    return this.gstLookedUp() && !this.gstOptions.length && !this.form.controls.gstin.value;
  }

  panForGst(): string {
    return (this.form.controls.pan.value || this.application.signatory.pan || '').toUpperCase();
  }

  minDirectorKyc(): number {
    return this.rules()?.needsCin ? 2 : 1;
  }

  verifiedDirectorCount(): number {
    return this.registryDirectors.filter((d) => d.kycVerified).length;
  }

  addressStepNumber(): number {
    let n = 2;
    if (this.rules()?.needsBusinessPan) n++;
    if (this.rules()?.needsCin) n++;
    return n;
  }

  gstStepNumber(): number {
    return this.addressStepNumber() + 1;
  }

  registryEntityType(): EntityType {
    return (this.form.controls.entityType.value || this.application.profile.entityType || 'partnership') as EntityType;
  }

  directorKey(director: RegistryDirector): string {
    return director.din || director.name;
  }

  directorKycDetails(director: RegistryDirector): { dob?: string; mobile?: string } | null {
    const details = director.digilocker?.userDetails;
    if (!details) {
      return null;
    }
    return { dob: details.dob, mobile: details.mobile };
  }

  directorKycLinkedFrom(director: RegistryDirector) {
    return directorKycLinkedFrom(director);
  }

  private loadRegistryDirectors(source: RegistryDirector[]): void {
    this.registryDirectors = syncDirectorsFromApplication(
      source.map((d) => ({
        mobile: '',
        digiConsent: false,
        kycVerified: false,
        ...d,
      })),
      this.application,
    );
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
    if (this.panCheck?.registeredName) {
      this.panDetails.set({
        verificationId: this.panCheck.verificationId,
        referenceId: this.panCheck.referenceId,
        status: this.panCheck.status as 'VALID' | 'INVALID',
        registeredName: this.panCheck.registeredName,
        pan: identity.pan,
        panType: '',
      });
    }
    if (this.cinCheck?.registeredName) {
      this.cinDetails.set({
        verificationId: this.cinCheck.verificationId,
        referenceId: this.cinCheck.referenceId,
        status: this.cinCheck.status as 'VALID' | 'INVALID',
        companyName: this.cinCheck.registeredName,
        cin: identity.cin,
        dateOfIncorporation: identity.doi,
        companyStatus: '',
      });
    }
    if (this.gstinCheck?.registeredName) {
      this.gstDetails.set({
        verificationId: this.gstinCheck.verificationId,
        referenceId: this.gstinCheck.referenceId,
        valid: this.gstinCheck.status === 'VALID',
        legalName: this.gstinCheck.registeredName,
        gstin: this.application.profile.gstin,
        taxpayerType: '',
        gstinStatus: this.gstinCheck.status === 'VALID' ? 'Active' : '',
      });
    }
    this.loadRegistryDirectors(this.application.registryDirectors ?? []);
    this.registryMembers = (this.application.registryMembers ?? []).map((m) => ({ ...m }));
    this.registryDeedDoc = this.application.registryDeedDoc;
    const kybIds = new Set(this.kybSlots.map((s) => s.id));
    this.kybDocs = this.application.documents.filter((d) => kybIds.has(d.slotId));
    const hinted = panEntityHint(this.form.controls.pan.value);
    if (hinted) {
      this.hint.set(ENTITY_LABELS[hinted]);
    }
    this.applyFieldValidators();
    this.applyRegistryLocks();
    this.restoreNameWarnings();
    if (this.showGst() && this.panForGst() && !this.gstLookedUp() && this.panLocked()) {
      this.fetchGstins(true);
    }
    if (this.readonly) {
      this.form.disable({ emitEvent: false });
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
    this.panAlert.set('');
    this.panWarning.set('');
    const legalHint =
      this.application.profile.legalName ||
      this.application.profile.brandName ||
      this.application.signatory.name ||
      '';
    this.verification.verifyPan(panValue, legalHint).subscribe({
      next: (result) => {
        this.panBusy.set(false);
        this.panDetails.set(result);
        this.panCheck = {
          verificationId: result.verificationId,
          referenceId: result.referenceId,
          status: result.status,
          registeredName: result.registeredName,
        };
        if (result.status !== 'VALID') {
          this.panAlert.set('PAN could not be verified. Check the number and try again.');
          return;
        }
        const hinted = panEntityHint(panValue);
        this.hint.set(hinted ? ENTITY_LABELS[hinted] : result.panType);
        this.mergeProfileNames(result.registeredName);
        this.panWarning.set(this.buildPanNameWarning(result, legalHint));
        const doi = result.incorporationDate || result.dateOfBirth || '';
        if (this.rules()?.needsDoi && doi) {
          this.form.controls.doi.setValue(doi);
        }
        this.applyRegistryLocks();
        this.fetchGstins(true);
      },
      error: (err: Error) => {
        this.panBusy.set(false);
        this.panAlert.set(err.message || 'PAN verification failed.');
      },
    });
  }

  fetchGstins(silent = false): void {
    const panValue = this.panForGst();
    if (!panValue || panValue.length < 10) {
      if (!silent) {
        this.gstAlert.set('Verify business PAN first to fetch GSTINs.');
      }
      return;
    }
    this.gstBusy.set(true);
    if (!silent) {
      this.gstAlert.set('');
    }
    this.verification.lookupGstinsByPan(panValue).subscribe({
      next: (result) => {
        this.gstBusy.set(false);
        this.gstLookedUp.set(true);
        this.gstOptions = result.gstins;
        this.form.controls.noGstin.setValue(false);
        if (!this.form.controls.gstin.value && result.gstins.length >= 1) {
          this.form.controls.gstin.setValue(result.gstins[0].gstin);
          this.onGstinPicked(true);
        }
        this.applyRegistryLocks();
      },
      error: (err: Error) => {
        this.gstBusy.set(false);
        if (!silent) {
          this.gstAlert.set(err.message || 'Could not fetch GSTINs for this PAN.');
        }
      },
    });
  }

  onGstinPicked(silent = false): void {
    if (this.form.controls.gstin.value) {
      this.form.controls.noGstin.setValue(false);
      this.verifyGstin(silent);
    }
  }

  verifyGstin(silent = false): void {
    const gstin = this.form.controls.gstin.value;
    if (!gstin) {
      return;
    }
    this.gstBusy.set(true);
    if (!silent) {
      this.gstAlert.set('');
      this.gstWarning.set('');
    }
    this.verification.verifyGstin(gstin).subscribe({
      next: (result) => {
        this.gstBusy.set(false);
        this.gstDetails.set(result);
        this.gstinCheck = {
          verificationId: result.verificationId,
          referenceId: result.referenceId,
          status: result.valid ? 'VALID' : 'INVALID',
          registeredName: result.legalName,
        };
        if (!result.valid) {
          if (!silent) {
            this.gstAlert.set('GSTIN verification failed.');
          }
          return;
        }
        this.mergeProfileNames(result.legalName);
        this.gstWarning.set(this.buildGstNameWarning(result.legalName));
        this.form.controls.noGstin.setValue(false);
        this.applyRegistryLocks();
      },
      error: (err: Error) => {
        this.gstBusy.set(false);
        if (!silent) {
          this.gstAlert.set(err.message || 'GSTIN verification failed.');
        }
      },
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
    this.cinAlert.set('');
    this.cinWarning.set('');
    this.verification.verifyCin(cin).subscribe({
      next: (result) => {
        this.cinBusy.set(false);
        this.cinDetails.set(result);
        this.cinCheck = {
          verificationId: result.verificationId,
          referenceId: result.referenceId,
          status: result.status,
          registeredName: result.companyName,
        };
        if (result.status !== 'VALID') {
          this.cinAlert.set('CIN verification failed.');
          return;
        }
        if (result.dateOfIncorporation) {
          this.form.controls.doi.setValue(result.dateOfIncorporation);
        }
        if (result.companyName) {
          this.mergeProfileNames(result.companyName);
        }
        this.cinWarning.set(this.buildCinNameWarning(result.companyName));
        if (result.directors?.length) {
          this.loadRegistryDirectors(result.directors);
        }
        if (result.registeredAddress) {
          this.forceAddress(this.form.controls.registeredAddress, result.registeredAddress);
        }
        this.applyRegistryLocks();
      },
      error: (err: Error) => {
        this.cinBusy.set(false);
        this.cinAlert.set(err.message || 'CIN verification failed.');
      },
    });
  }

  verifyDirectorKyc(director: RegistryDirector): void {
    const pan = (director.pan || '').trim().toUpperCase();
    const mobile = (director.mobile || '').trim();
    if (!PAN_PATTERN.test(pan)) {
      this.directorAlert.set(`Enter a valid PAN for ${director.name}.`);
      return;
    }
    director.pan = pan;
    if (!MOBILE_PATTERN.test(mobile)) {
      this.directorAlert.set(`Enter the DigiLocker mobile for ${director.name}.`);
      return;
    }
    if (!director.digiConsent) {
      this.directorAlert.set('DigiLocker consent is required for director KYC.');
      return;
    }
    this.directorAlert.set('');
    const key = this.directorKey(director);
    this.directorKycBusy.set(key);
    this.directorKycLabel.set('Opening DigiLocker…');
    this.digilockerSession.run({ mobile, pan, name: director.name }).subscribe({
      next: (status) => {
        this.directorKycBusy.set('');
        this.applyDirectorDigilockerStatus(director, status);
      },
      error: (err: Error) => {
        this.directorKycBusy.set('');
        this.directorAlert.set(err.message || 'Director KYC failed.');
      },
    });
  }

  refreshDirectorKyc(director: RegistryDirector): void {
    const verificationId = director.digilocker?.verificationId;
    if (!verificationId) {
      return;
    }
    this.directorAlert.set('');
    const key = this.directorKey(director);
    this.directorKycBusy.set(key);
    this.directorKycLabel.set('Refreshing…');
    this.digilockerSession.sync(verificationId, director.pan, director.name).subscribe({
      next: (status) => {
        this.directorKycBusy.set('');
        this.applyDirectorDigilockerStatus(director, status);
      },
      error: (err: Error) => {
        this.directorKycBusy.set('');
        this.directorAlert.set(err.message || 'Could not refresh DigiLocker status.');
      },
    });
  }

  private applyDirectorDigilockerStatus(director: RegistryDirector, status: DigilockerStatusResult): void {
    director.digilocker = status;
    if (status.status !== 'AUTHENTICATED') {
      this.directorAlert.set('DigiLocker still pending. Finish consent, then click Refresh status.');
      return;
    }
    const name = status.userDetails?.name || status.documents.find((d) => d.type === 'AADHAAR')?.name;
    if (name) {
      director.name = name;
    }
    director.kycVerified = true;
    director.kycPath = 'digilocker';
    this.directorAlert.set('');
  }

  onRegistryMembersChange(members: RegistryDirector[]): void {
    this.registryMembers = members;
  }

  back(): void {
    this.save.emit({
      ...this.withIdentity(),
      currentStep: onboardingNav(this.application).prev('identity'),
    });
  }

  next(): void {
    this.applyFieldValidators();
    this.submitError.set('');
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.submitError.set('Complete all required fields before continuing.');
      scrollToFeedback(this.submitFeedback?.nativeElement);
      return;
    }
    if (this.rules()?.needsBusinessPan && !this.panLocked()) {
      this.submitError.set('Verify the business PAN before continuing.');
      scrollToFeedback(this.submitFeedback?.nativeElement);
      return;
    }
    if (this.rules()?.needsCin && !this.cinLocked()) {
      this.submitError.set('Verify the CIN before continuing.');
      scrollToFeedback(this.submitFeedback?.nativeElement);
      return;
    }
    if (this.rules()?.needsPartnerRegistry && this.registryMembers.length < 2) {
      this.submitError.set('Add at least two partners or trustees before continuing.');
      scrollToFeedback(this.submitFeedback?.nativeElement);
      return;
    }
    if (this.rules()?.needsCin && this.verifiedDirectorCount() < this.minDirectorKyc()) {
      this.submitError.set(`Complete DigiLocker KYC for at least ${this.minDirectorKyc()} directors from the MCA record.`);
      scrollToFeedback(this.submitFeedback?.nativeElement);
      return;
    }
    if (!this.addressLocked()) {
      this.submitError.set(
        this.rules()?.addressFromCin
          ? 'Registered office loads after CIN verification.'
          : 'Complete the registered office address before continuing.',
      );
      scrollToFeedback(this.submitFeedback?.nativeElement);
      return;
    }
    if (this.form.controls.gstin.value && this.gstinCheck?.status !== 'VALID') {
      this.submitError.set('Verify the GSTIN before continuing.');
      scrollToFeedback(this.submitFeedback?.nativeElement);
      return;
    }
    if (this.showGst() && !this.form.controls.gstin.value && this.showNoGstinOption()) {
      if (!this.form.controls.noGstin.value) {
        this.submitError.set('Confirm that this entity is not registered under GST, or fetch GSTINs again.');
        scrollToFeedback(this.submitFeedback?.nativeElement);
        return;
      }
    }
    if (this.showGst() && !this.form.controls.noGstin.value && !this.form.controls.gstin.value && this.panLocked()) {
      if (!this.gstLookedUp()) {
        this.fetchGstins();
      }
      this.submitError.set('Select and verify a GSTIN from the PAN list.');
      scrollToFeedback(this.submitFeedback?.nativeElement);
      return;
    }
    const missing = this.kybSlots.filter((s) => s.required && !this.doc(s.id));
    if (missing.length) {
      this.submitError.set(`Upload: ${missing.map((s) => s.label).join(', ')}`);
      scrollToFeedback(this.submitFeedback?.nativeElement);
      return;
    }
    this.save.emit({
      ...this.withIdentity(),
      currentStep: onboardingNav(this.application).next('identity'),
    });
  }

  private registryLegalName(): string {
    return (
      this.panCheck?.registeredName ||
      this.panDetails()?.registeredName ||
      this.application.profile.legalName ||
      ''
    );
  }

  private buildPanNameWarning(result: PanVerifyResult, expected: string): string {
    if (result.nameMatchWarning) {
      const match = result.nameMatch || 'PARTIAL';
      return `PAN name "${result.registeredName}" does not fully match the name you provided (${match.replace('_', ' ').toLowerCase()}). Confirm this is the correct entity.`;
    }
    if (expected && namesClearlyDiffer(result.registeredName, expected)) {
      return `PAN legal name "${result.registeredName}" differs from "${expected.trim()}". Confirm this is the correct business entity.`;
    }
    return '';
  }

  private buildCinNameWarning(companyName: string): string {
    const panName = this.registryLegalName();
    if (panName && namesClearlyDiffer(companyName, panName)) {
      return `MCA company name "${companyName}" differs from PAN name "${panName}". Review before continuing — mismatched names often cause rejection.`;
    }
    return '';
  }

  private buildGstNameWarning(gstLegalName: string): string {
    const panName = this.registryLegalName();
    if (panName && namesClearlyDiffer(gstLegalName, panName)) {
      return `GST legal name "${gstLegalName}" differs from PAN name "${panName}". Use the same legal name across PAN, CIN, and GST.`;
    }
    return '';
  }

  private restoreNameWarnings(): void {
    const legalHint =
      this.application.profile.legalName ||
      this.application.profile.brandName ||
      this.application.signatory.name ||
      '';
    const pan = this.panDetails();
    if (this.panLocked() && pan) {
      this.panWarning.set(this.buildPanNameWarning(pan, legalHint));
    }
    const cin = this.cinDetails();
    if (this.cinLocked() && cin?.companyName) {
      this.cinWarning.set(this.buildCinNameWarning(cin.companyName));
    }
    const gst = this.gstDetails();
    if (this.gstLocked() && gst?.legalName) {
      this.gstWarning.set(this.buildGstNameWarning(gst.legalName));
    }
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

  private applyRegistryLocks(): void {
    if (this.readonly) {
      return;
    }
    if (this.panLocked()) {
      this.form.controls.pan.disable({ emitEvent: false });
      this.form.controls.doi.disable({ emitEvent: false });
    }
    if (this.cinLocked()) {
      this.form.controls.cin.disable({ emitEvent: false });
      this.form.controls.doi.disable({ emitEvent: false });
    }
    if (this.addressLocked()) {
      this.form.controls.registeredAddress.disable({ emitEvent: false });
    }
    if (this.gstLocked()) {
      this.form.controls.gstin.disable({ emitEvent: false });
    }
  }

  private withIdentity(): KycApplication {
    const raw = this.form.getRawValue();
    const keep = this.application.documents.filter((d) => !this.kybSlots.some((s) => s.id === d.slotId));
    const hasGst = !!raw.gstin && this.gstLocked();
    const noGstin = this.showGst() && !hasGst ? raw.noGstin : false;
    const legalName =
      this.application.profile.legalName ||
      this.panCheck?.registeredName ||
      this.gstinCheck?.registeredName ||
      this.cinCheck?.registeredName ||
      '';
    const brandName = this.application.profile.brandName || legalName;
    const ubosFromDirectors = this.registryDirectors.map((d) => ({
      id: d.din || d.name,
      name: d.name,
      pan: d.pan || '',
      ownershipPercent: 0,
      relationship: d.designation || 'Director',
      kycVerified: !!d.kycVerified,
      kycPath: d.kycPath,
    }));
    const ubosFromMembers = this.registryMembers.map((m) => ({
      id: m.pan || m.name,
      name: m.name,
      pan: m.pan || '',
      ownershipPercent: 0,
      relationship: m.designation || 'Partner',
      kycVerified: !!m.kycVerified,
      kycPath: m.kycPath,
    }));
    const mergedUbos = ubosFromMembers.length ? ubosFromMembers : ubosFromDirectors;
    return {
      ...this.application,
      profile: {
        ...this.application.profile,
        entityType: raw.entityType,
        legalName,
        brandName,
        gstin: noGstin ? '' : raw.gstin,
        noGstin,
        gstinOptions: this.gstOptions,
      },
      registryDirectors: this.registryDirectors.map(({ mobile, digiConsent, digilocker, ...d }) => d),
      registryMembers: this.registryMembers.map(({ mobile, digiConsent, digilocker, ...m }) => m),
      registryDeedDoc: this.registryDeedDoc,
      ubos: mergedUbos.length ? mergedUbos : this.application.ubos,
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

  private mergeProfileNames(name: string): void {
    const trimmed = (name || '').trim();
    if (!trimmed) {
      return;
    }
    this.application = {
      ...this.application,
      profile: {
        ...this.application.profile,
        legalName: this.application.profile.legalName || trimmed,
        brandName: this.application.profile.brandName || trimmed,
      },
    };
  }

  private forceAddress(group: FormGroup, addr: Partial<Address>): void {
    group.patchValue({
      line1: addr.line1 || '',
      line2: addr.line2 || '',
      city: addr.city || '',
      state: addr.state || '',
      pin: addr.pin || '',
    });
  }
}
