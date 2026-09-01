import { CurrencyPipe, DatePipe, TitleCasePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { documentsFor } from '../../core/config/entity-documents';
import { authorisationSlotId, needsOwnerPersonKyc } from '../../core/config/entity-rules';
import { SIGNATORY_RELATION_LABELS } from '../../core/config/signatory-relations';
import {
  Address,
  ENTITY_LABELS,
  KycApplication,
  PARTNER_TYPE_LABELS,
  SignatoryKyc,
  UploadedDoc,
} from '../../core/models/onboarding.models';
import { OnboardingService } from '../../core/services/onboarding.service';
import { AuthService } from '../../core/services/auth.service';
import { StatusChipComponent } from '../../shared/ui/status-chip/status-chip.component';

interface FileRow {
  group: string;
  label: string;
  file?: UploadedDoc;
}

@Component({
  selector: 'app-admin-partner-file',
  standalone: true,
  imports: [
    DatePipe,
    CurrencyPipe,
    TitleCasePipe,
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule,
    StatusChipComponent,
  ],
  template: `
    <p class="back"><a routerLink="/admin/partners">← All partners</a></p>
    @if (row(); as partner) {
      <article class="hero">
        <div>
          <h2>{{ partner.application?.profile?.brandName || partner.user.fullName }}</h2>
          <p>
            {{ typeLabel(partner.user.partnerType) }} · {{ partner.user.email }} · {{ partner.user.mobile }}
          </p>
        </div>
        @if (partner.application) {
          <app-status-chip [status]="partner.application.status" />
        }
      </article>

      @if (app(); as application) {
        <div class="grid">
          <section>
            <h3>Business</h3>
            <dl>
              <div><dt>Legal name</dt><dd>{{ application.profile.legalName || '—' }}</dd></div>
              <div>
                <dt>Entity</dt>
                <dd>{{ application.profile.entityType ? labels[application.profile.entityType] : '—' }}</dd>
              </div>
              <div><dt>Category</dt><dd>{{ application.profile.category || '—' }}</dd></div>
              <div><dt>Website</dt><dd>{{ application.profile.website || '—' }}</dd></div>
              <div><dt>Volume</dt><dd>{{ application.profile.monthlyVolume || '—' }}</dd></div>
              <div><dt>GSTIN</dt><dd>{{ application.profile.noGstin ? 'Not enrolled' : application.profile.gstin || '—' }}</dd></div>
              @if (application.profile.gstinOptions?.length) {
                <div>
                  <dt>GSTINs on PAN</dt>
                  <dd>{{ gstinList(application) }}</dd>
                </div>
              }
            </dl>
          </section>
          <section>
            <h3>KYB registry</h3>
            <dl>
              <div><dt>Business PAN</dt><dd>{{ application.identity.pan || '—' }} · {{ application.identity.panCheck?.status || 'unverified' }}</dd></div>
              <div><dt>CIN / LLPIN</dt><dd>{{ application.identity.cin || application.identity.llpin || '—' }}</dd></div>
              <div><dt>Incorporation</dt><dd>{{ application.identity.doi || '—' }}</dd></div>
              <div><dt>Registered office</dt><dd>{{ formatAddress(application.identity.registeredAddress) }}</dd></div>
              <div><dt>Operating address</dt><dd>{{ application.identity.sameAsRegistered ? 'Same as registered' : formatAddress(application.identity.operatingAddress) }}</dd></div>
            </dl>
          </section>
          <section>
            <h3>Authorised signatory</h3>
            <dl>
              <div><dt>Name</dt><dd>{{ application.signatory.name || '—' }}</dd></div>
              <div><dt>PAN</dt><dd>{{ application.signatory.pan || '—' }}</dd></div>
              <div><dt>Mobile</dt><dd>{{ application.signatory.mobile || '—' }}</dd></div>
              <div><dt>KYC</dt><dd>{{ application.signatory.verified ? 'Verified (DigiLocker + scans)' : 'Pending' }}</dd></div>
              <div>
                <dt>Relation to business</dt>
                <dd>{{ relationLabel(application.signatoryRelation) }}</dd>
              </div>
              <div>
                <dt>KYC person is authorised signatory</dt>
                <dd>
                  {{
                    application.kycPersonIsAuthorisedSignatory === false
                      ? 'No — authorised signatory is ' + (application.authorisedSignatoryName || '—')
                      : application.kycPersonIsAuthorisedSignatory
                        ? 'Yes'
                        : '—'
                  }}
                </dd>
              </div>
              <div>
                <dt>Role</dt>
                <dd>
                  {{
                    application.signatoryIsOwner === false
                      ? 'Authorised signatory only — not an owner'
                      : application.signatoryIsOwner
                        ? 'Director / owner and authorised signatory'
                        : '—'
                  }}
                </dd>
              </div>
            </dl>
            @for (doc of application.signatory.digilocker?.documents ?? []; track doc.type) {
              <p class="fetched">{{ doc.type }} · {{ doc.name }} · {{ doc.idMasked }}</p>
            }
          </section>
          @if (needsOwner(application)) {
            <section>
              <h3>Business owner KYC</h3>
              <dl>
                <div><dt>Name</dt><dd>{{ application.ownerKyc.name || '—' }}</dd></div>
                <div><dt>PAN</dt><dd>{{ application.ownerKyc.pan || '—' }}</dd></div>
                <div><dt>Mobile</dt><dd>{{ application.ownerKyc.mobile || '—' }}</dd></div>
                <div><dt>KYC</dt><dd>{{ application.ownerKyc.verified ? 'Verified' : 'Missing' }}</dd></div>
              </dl>
            </section>
          }
          <section>
            <h3>Beneficial owners</h3>
            @if (application.publicListedSkip) {
              <p>Listed-company UBO skip declared.</p>
            } @else if (!application.ubos.length) {
              <p>None listed.</p>
            } @else {
              <ul>
                @for (ubo of application.ubos; track ubo.id) {
                  <li>{{ ubo.name }} · {{ ubo.pan }} · {{ ubo.ownershipPercent }}% · {{ ubo.relationship }} · {{ ubo.kycVerified ? 'KYC done' : 'KYC pending' }}</li>
                }
              </ul>
            }
          </section>
          <section>
            <h3>Bank</h3>
            <dl>
              <div><dt>Holder</dt><dd>{{ application.bank.holderName || '—' }}</dd></div>
              <div><dt>Account</dt><dd>{{ application.bank.accountNumber || '—' }}</dd></div>
              <div><dt>IFSC</dt><dd>{{ application.bank.ifsc || '—' }}</dd></div>
              <div><dt>Bank</dt><dd>{{ application.bank.bankName || '—' }} {{ application.bank.branch }}</dd></div>
              <div><dt>Penny drop</dt><dd>{{ application.bank.pennyDropStatus | titlecase }}</dd></div>
            </dl>
          </section>
          <section>
            <h3>Agreement</h3>
            <dl>
              <div><dt>Partner signed</dt><dd>{{ application.agreement.signedAt ? (application.agreement.signedAt | date: 'medium') : 'No' }}</dd></div>
              <div><dt>Admin signed</dt><dd>{{ application.agreement.adminSignedAt ? (application.agreement.adminSignedAt | date: 'medium') : 'No' }}</dd></div>
              <div><dt>Submitted</dt><dd>{{ application.submittedAt ? (application.submittedAt | date: 'medium') : '—' }}</dd></div>
            </dl>
          </section>
        </div>

        <section class="docs">
          <h3>Documents</h3>
          <p class="hint">
            Review every scan before approval. Board resolution is mandatory for companies and LLPs
            even when the signatory is a director.
            @if (authSlot()) {
              Required instrument: <strong>{{ authSlot() }}</strong>.
            }
          </p>
          <div class="files">
            @for (row of files(); track row.group + row.label) {
              <article>
                <p class="group">{{ row.group }}</p>
                <strong>{{ row.label }}</strong>
                <span>{{ row.file?.fileName || 'Not uploaded' }}</span>
                @if (row.file?.dataUrl; as src) {
                  @if (row.file?.mimeType?.startsWith('image/')) {
                    <img [src]="src" [alt]="row.label" />
                  } @else {
                    <a [href]="src" target="_blank" rel="noopener">Open file</a>
                  }
                } @else if (row.file) {
                  <em>Preview available after the partner re-uploads in this browser.</em>
                }
              </article>
            }
          </div>
        </section>

        @if (application.status === 'under_review') {
          <section class="review">
            <h3>Compliance review</h3>
            <p>Approve only after you have opened this file. Demo partners may have seed filenames without image preview.</p>
            <mat-checkbox [checked]="sawSignatory()" (change)="sawSignatory.set($event.checked)">Authorised-signatory KYC reviewed</mat-checkbox>
            <mat-checkbox [checked]="sawOwner()" (change)="sawOwner.set($event.checked)">Business-owner KYC reviewed (or not applicable)</mat-checkbox>
            <mat-checkbox [checked]="sawDocs()" (change)="sawDocs.set($event.checked)">Entity documents and board resolution reviewed</mat-checkbox>
            <mat-checkbox [checked]="sawBank()" (change)="sawBank.set($event.checked)">Bank details match the legal name</mat-checkbox>
            <div class="actions">
              <button
                mat-flat-button
                color="primary"
                type="button"
                [disabled]="!canApprove()"
                (click)="approve(partner.user.id)"
              >
                Approve KYC / KYB
              </button>
            </div>
            <mat-form-field appearance="outline" class="wide">
              <mat-label>Return reason</mat-label>
              <textarea matInput rows="2" [(ngModel)]="returnReason"></textarea>
            </mat-form-field>
            <button mat-stroked-button color="warn" type="button" (click)="reject(partner.user.id)">
              Send back to partner
            </button>
          </section>
        }
        @if (application.status === 'pending_admin_sign') {
          <section class="review">
            <h3>Countersign</h3>
            <p>Partner has e-signed. Countersign only after the file above is still accurate.</p>
            <button mat-flat-button color="primary" type="button" (click)="countersign(partner.user.id)">
              Countersign agreement
            </button>
          </section>
        }
      } @else {
        <p>No onboarding file yet.</p>
      }

      <section class="orders">
        <h3>Orders</h3>
        @if (partnerOrders().length) {
          <table>
            <thead>
              <tr>
                <th>Order</th>
                <th>PO</th>
                <th>Product</th>
                <th>Amount</th>
                <th>Mode</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              @for (row of partnerOrders(); track row.id) {
                <tr>
                  <td>
                    <a [routerLink]="['/admin/orders', row.id]"><code>{{ row.id }}</code></a>
                    <div>{{ row.createdAt | date: 'short' }}</div>
                  </td>
                  <td>{{ row.poNumber || '—' }}</td>
                  <td>{{ row.title }} · {{ row.brand }} × {{ row.quantity }}</td>
                  <td>{{ row.amount | currency: 'INR' : 'symbol' : '1.0-0' }}</td>
                  <td>{{ row.mode === 'test' ? 'Test' : 'Live' }}</td>
                  <td>{{ row.status | titlecase }}</td>
                </tr>
              }
            </tbody>
          </table>
        } @else {
          <p>No orders for this partner.</p>
        }
      </section>
    } @else {
      <p>Partner not found.</p>
    }
    @if (message()) {
      <p class="msg">{{ message() }}</p>
    }
  `,
  styles: [
    `
      .back {
        margin: 0 0 12px;
      }
      .hero,
      section {
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 16px;
        padding: 18px;
        margin-bottom: 12px;
      }
      .hero {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: start;
      }
      h2,
      h3 {
        margin: 0 0 8px;
      }
      .grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
      }
      dl {
        display: grid;
        gap: 8px;
        margin: 0;
      }
      dt {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #8a819d;
      }
      dd {
        margin: 2px 0 0;
        font-weight: 650;
      }
      .fetched,
      .hint,
      li,
      span,
      em {
        font-size: 13px;
        color: #6d6484;
      }
      .files {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
        margin-top: 12px;
      }
      .files article {
        border: 1px solid #efeaf8;
        border-radius: 12px;
        padding: 12px;
        display: grid;
        gap: 4px;
      }
      .group {
        margin: 0;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #8a819d;
        font-weight: 700;
      }
      img {
        width: 100%;
        max-height: 160px;
        object-fit: contain;
        border-radius: 8px;
        background: #f6f3fb;
      }
      .review {
        display: grid;
        gap: 10px;
      }
      .wide {
        width: 100%;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }
      th,
      td {
        text-align: left;
        padding: 10px 6px;
        border-bottom: 1px solid #f0ebf7;
        vertical-align: top;
      }
      th {
        color: #8a819d;
        font-size: 11px;
        text-transform: uppercase;
      }
      code,
      td div {
        color: #8a819d;
        font-size: 12px;
      }
      .msg {
        color: #0f7a3d;
        font-weight: 650;
      }
      @media (max-width: 960px) {
        .grid,
        .files {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class AdminPartnerFileComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  readonly onboarding = inject(OnboardingService);
  private readonly auth = inject(AuthService);
  readonly labels = ENTITY_LABELS;
  readonly message = signal('');
  readonly sawSignatory = signal(false);
  readonly sawOwner = signal(false);
  readonly sawDocs = signal(false);
  readonly sawBank = signal(false);
  returnReason = '';

  readonly row = computed(() => {
    const id = this.route.snapshot.paramMap.get('userId');
    return this.onboarding.partners().find((p) => p.user.id === id) ?? null;
  });

  readonly app = computed(() => this.row()?.application ?? null);
  readonly partnerOrders = computed(() => {
    const id = this.row()?.user.id;
    return id ? this.onboarding.orders().filter((o) => o.userId === id) : [];
  });

  ngOnInit(): void {
    this.onboarding.loadPartners().subscribe();
    this.onboarding.loadOrders().subscribe();
  }

  typeLabel(type: string): string {
    if (type === 'corporate') {
      return PARTNER_TYPE_LABELS[type];
    }
    return type;
  }

  relationLabel(id: string): string {
    return SIGNATORY_RELATION_LABELS[id as keyof typeof SIGNATORY_RELATION_LABELS] || id || '—';
  }

  gstinList(app: KycApplication): string {
    return (app.profile.gstinOptions ?? []).map((item) => item.gstin).join(', ') || '—';
  }

  needsOwner(app: KycApplication): boolean {
    return needsOwnerPersonKyc(app);
  }

  authSlot(): string | null {
    const app = this.app();
    return app ? authorisationSlotId(app.profile.entityType) : null;
  }

  files(): FileRow[] {
    const application = this.app();
    if (!application) {
      return [];
    }
    const rows: FileRow[] = [];
    const pushPerson = (group: string, person: SignatoryKyc, panId: string, idSlot: string) => {
      rows.push({ group, label: 'PAN card', file: person.docs.find((d) => d.slotId === panId) });
      rows.push({ group, label: 'Photo ID', file: person.docs.find((d) => d.slotId === idSlot) });
    };
    pushPerson('Authorised signatory', application.signatory, 'signatory_pan', 'signatory_id');
    if (needsOwnerPersonKyc(application)) {
      pushPerson('Business owner', application.ownerKyc, 'owner_pan', 'owner_id');
    }
    for (const slot of documentsFor(application.profile.entityType, application.profile.category, true)) {
      const file =
        application.documents.find((d) => d.slotId === slot.id) ||
        (slot.id === 'bank_proof' ? application.bank.proofFile : undefined);
      rows.push({ group: 'Entity / bank', label: slot.label, file });
    }
    return rows;
  }

  formatAddress(address: Address): string {
    const parts = [address.line1, address.line2, address.city, address.state, address.pin].filter(Boolean);
    return parts.join(', ') || '—';
  }

  canApprove(): boolean {
    return this.sawSignatory() && this.sawOwner() && this.sawDocs() && this.sawBank();
  }

  approve(userId: string): void {
    this.onboarding.adminApproveKyc(userId).subscribe({
      next: () => this.message.set('KYC / KYB approved. Partner can e-sign.'),
      error: (err: Error) => this.message.set(err.message),
    });
  }

  reject(userId: string): void {
    const reason = this.returnReason.trim() || 'Please revise documents and resubmit.';
    this.onboarding.adminRejectKyc(userId, reason).subscribe({
      next: () => this.message.set('Sent back to partner as draft.'),
      error: (err: Error) => this.message.set(err.message),
    });
  }

  countersign(userId: string): void {
    const name = this.auth.user()?.fullName || 'Payswap Admin';
    this.onboarding.adminCountersign(userId, name).subscribe({
      next: () => this.message.set('Agreement countersigned. Partner is live.'),
      error: (err: Error) => this.message.set(err.message),
    });
  }
}
