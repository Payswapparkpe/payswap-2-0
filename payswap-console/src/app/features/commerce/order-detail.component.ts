import { CurrencyPipe, DatePipe, TitleCasePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { FulfilmentFile, PartnerOrder } from '../../core/models/onboarding.models';
import {
  downloadDataUrl,
  downloadText,
  invoiceHtml,
  kindLabel,
  lockedFileText,
  trackerSteps,
} from '../../core/config/order.util';
import { OnboardingService } from '../../core/services/onboarding.service';
import { AuthService } from '../../core/services/auth.service';
import { OtpService } from '../../core/services/otp.service';
import { OtpInputComponent } from '../../shared/ui/otp-input/otp-input.component';

@Component({
  selector: 'app-order-detail',
  standalone: true,
  imports: [CurrencyPipe, DatePipe, TitleCasePipe, RouterLink, MatButtonModule, ReactiveFormsModule, OtpInputComponent],
  template: `
    <p class="back">
      <a [routerLink]="isAdmin() ? '/admin/orders' : '/app/orders'">← All orders</a>
    </p>
    @if (error()) {
      <p class="error">{{ error() }}</p>
    }
    @if (order(); as row) {
      <article class="hero">
        <div>
          <p class="id">{{ row.id }}</p>
          <h2>{{ row.title }}</h2>
          <p>{{ kindLabel(row.kind) }} · {{ row.brand }}</p>
        </div>
        <span class="mode" [class.test]="row.mode === 'test'">{{ row.mode === 'test' ? 'Test' : 'Live' }}</span>
      </article>

      <ol class="tracker">
        @for (step of steps(); track step.id) {
          <li [class]="step.state">
            <span>{{ step.label }}</span>
          </li>
        }
      </ol>

      <div class="grid">
        <section>
          <h3>Order</h3>
          <dl>
            <div><dt>Product</dt><dd>{{ row.title }}</dd></div>
            <div><dt>Denomination</dt><dd>{{ row.unitValue | currency: 'INR' : 'symbol' : '1.0-0' }}</dd></div>
            <div><dt>Quantity</dt><dd>{{ row.quantity }}</dd></div>
            <div><dt>Amount</dt><dd>{{ row.amount | currency: 'INR' : 'symbol' : '1.0-0' }}</dd></div>
            <div><dt>Note</dt><dd>{{ row.note || '—' }}</dd></div>
            <div><dt>Partner</dt><dd>{{ partnerLabel(row) }}</dd></div>
            <div><dt>Placed</dt><dd>{{ row.createdAt | date: 'medium' }}</dd></div>
            <div><dt>Updated</dt><dd>{{ row.updatedAt | date: 'medium' }}</dd></div>
            <div><dt>Invoice</dt><dd>{{ row.invoiceId }}</dd></div>
            <div><dt>PO</dt><dd>{{ row.poNumber || '—' }}</dd></div>
          </dl>
          <div class="actions">
            <button mat-stroked-button type="button" (click)="downloadInvoice(row)">Download invoice</button>
            @if (row.status === 'fulfilled' && row.fulfilmentCodes.length) {
              <button mat-stroked-button type="button" (click)="downloadCodes(row)">Download codes</button>
            }
            @if (!isAdmin() && row.status === 'placed') {
              <button mat-stroked-button color="warn" type="button" [disabled]="busy()" (click)="cancel()">
                Cancel order
              </button>
            }
            @if (!isAdmin() && row.kind !== 'corporate_gifting') {
              <a mat-stroked-button [routerLink]="againLink(row)">Order again</a>
            }
            @if (isAdmin() && row.status === 'placed') {
              <button mat-flat-button color="primary" type="button" [disabled]="busy()" (click)="setStatus('processing')">
                Mark processing
              </button>
            }
            @if (isAdmin() && (row.status === 'placed' || row.status === 'processing')) {
              <button mat-stroked-button color="warn" type="button" [disabled]="busy()" (click)="setStatus('cancelled')">
                Cancel
              </button>
              <button mat-stroked-button type="button" [disabled]="busy()" (click)="setStatus('fulfilled')">
                Fulfil without file
              </button>
            }
          </div>
        </section>
        <section>
          <h3>Timeline</h3>
          <ul class="events">
            @for (event of row.timeline; track event.at + event.status) {
              <li>
                <strong>{{ event.status | titlecase }}</strong>
                <span>{{ event.at | date: 'short' }}</span>
                <p>{{ event.note }}</p>
              </li>
            }
          </ul>
          @if (row.status === 'fulfilled') {
            <h3>Fulfilment</h3>
            @if (row.kind === 'prepaid_card') {
              <p class="hint">Demo card kit references. Live issuance would ship physical kits or wallet loads.</p>
            } @else {
              <p class="hint">Demo voucher codes (capped sample). Full quantity would be delivered by CSV or API.</p>
            }
            <ul class="codes">
              @for (code of row.fulfilmentCodes; track code) {
                <li><code>{{ code }}</code></li>
              }
            </ul>
          }
        </section>
      </div>

      <section>
        <h3>Fulfilment file</h3>
        @if (isAdmin() && (row.status === 'placed' || row.status === 'processing')) {
          <p class="hint">Upload the brand voucher / card file. Payswap generates a password, mails a locked copy, and partners reveal it after email OTP verification.</p>
          <input type="file" (change)="onFile($event)" />
          @if (pendingFileName()) {
            <p>Selected: {{ pendingFileName() }}</p>
          }
          <button mat-flat-button color="primary" type="button" [disabled]="busy() || !pendingFile()" (click)="uploadFile()">
            {{ busy() ? 'Sending…' : 'Mail protected file and fulfil' }}
          </button>
        }
        @if (row.fulfilmentFile) {
          <p>Attachment: <strong>{{ row.fulfilmentFile.fileName }}</strong></p>
          <button mat-stroked-button type="button" (click)="downloadLocked(row)">Download locked copy</button>
        }
        @if (isAdmin() && row.filePassword) {
          <p class="pwd">File password: <code>{{ row.filePassword }}</code></p>
        }
        @if (!isAdmin() && row.fulfilmentFile) {
          @if (!revealed()) {
            <p class="hint">
              Request an OTP on {{ auth.user()?.email }}. Mobile OTP for other flows uses Kaleyra SMS ({{ otp.config().smsSender }}).
            </p>
            <button mat-stroked-button type="button" [disabled]="busy()" (click)="sendOtp()">Send OTP</button>
            @if (otpSent()) {
              <p class="label">OTP</p>
              <app-otp-input [formControl]="otpCtrl" />
              <button mat-flat-button color="primary" type="button" [disabled]="busy()" (click)="reveal()">
                Reveal password
              </button>
            }
          } @else {
            <p class="pwd">File password: <code>{{ revealedPassword() }}</code></p>
            <button mat-flat-button color="primary" type="button" (click)="downloadReal()">Download real file</button>
          }
        }
        @if (row.status === 'fulfilled' && row.fulfilmentCodes.length && !row.fulfilmentFile) {
          <p class="hint">No file was attached. Sample codes are below.</p>
        }
      </section>
    } @else if (!error()) {
      <p>Loading order…</p>
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
      .id {
        margin: 0;
        color: #8a819d;
        font-size: 12px;
      }
      h2,
      h3 {
        margin: 4px 0 6px;
      }
      .mode {
        background: #efe7ff;
        color: #5b21b6;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        padding: 6px 10px;
        border-radius: 999px;
      }
      .mode.test {
        background: #fff4e8;
        color: #b45309;
      }
      .tracker {
        list-style: none;
        display: flex;
        gap: 8px;
        padding: 0;
        margin: 0 0 12px;
      }
      .tracker li {
        flex: 1;
        text-align: center;
        padding: 10px 8px;
        border-radius: 12px;
        background: #f6f3fb;
        color: #8a819d;
        font-weight: 700;
        font-size: 13px;
      }
      .tracker li.done,
      .tracker li.active {
        background: linear-gradient(100deg, #fe881b, #ac24ff);
        color: #fff;
      }
      .tracker li.todo {
        opacity: 0.7;
      }
      .grid {
        display: grid;
        grid-template-columns: 1.1fr 0.9fr;
        gap: 12px;
      }
      dl {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin: 0 0 16px;
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
      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .events,
      .codes {
        list-style: none;
        margin: 0;
        padding: 0;
        display: grid;
        gap: 10px;
      }
      .events span,
      .hint {
        display: block;
        color: #8a819d;
        font-size: 12px;
      }
      .events p {
        margin: 4px 0 0;
      }
      .pwd {
        font-weight: 700;
      }
      .label {
        margin: 10px 0 4px;
        font-size: 12px;
        color: #8a819d;
      }
      @media (max-width: 860px) {
        .grid,
        dl,
        .tracker {
          grid-template-columns: 1fr;
          display: grid;
        }
      }
    `,
  ],
})
export class OrderDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly onboarding = inject(OnboardingService);
  readonly auth = inject(AuthService);
  readonly otp = inject(OtpService);

  readonly order = signal<PartnerOrder | null>(null);
  readonly error = signal('');
  readonly busy = signal(false);
  readonly isAdmin = computed(() => this.router.url.startsWith('/admin'));
  readonly steps = computed(() => {
    const row = this.order();
    return row ? trackerSteps(row.status) : [];
  });
  readonly kindLabel = kindLabel;
  readonly otpCtrl = new FormControl('', { nonNullable: true });
  readonly otpSent = signal(false);
  readonly revealed = signal(false);
  readonly revealedPassword = signal('');
  readonly pendingFile = signal<FulfilmentFile | null>(null);
  readonly pendingFileName = signal('');

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      const id = params.get('orderId');
      if (id) {
        this.load(id);
      }
    });
    if (this.isAdmin()) {
      this.onboarding.loadPartners().subscribe();
    }
  }

  partnerLabel(row: PartnerOrder): string {
    if (row.legalName) {
      return row.legalName;
    }
    const hit = this.onboarding.partners().find((p) => p.user.id === row.userId);
    return hit?.application?.profile.legalName || hit?.user.fullName || this.auth.user()?.fullName || 'Partner';
  }

  againLink(row: PartnerOrder): string {
    return row.kind === 'prepaid_card' ? '/app/cards' : '/app/vouchers';
  }

  downloadInvoice(row: PartnerOrder): void {
    downloadText(`${row.invoiceId}.html`, invoiceHtml(row, this.partnerLabel(row)), 'text/html');
  }

  downloadCodes(row: PartnerOrder): void {
    const body = ['code', ...row.fulfilmentCodes].join('\n');
    downloadText(`${row.id}-codes.csv`, body, 'text/csv');
  }

  downloadLocked(row: PartnerOrder): void {
    downloadText(`${row.id}-LOCKED.txt`, lockedFileText(row), 'text/plain');
  }

  onFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) {
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      this.pendingFile.set({
        fileName: file.name,
        mimeType: file.type || 'application/octet-stream',
        dataUrl: String(reader.result || ''),
      });
      this.pendingFileName.set(file.name);
    };
    reader.readAsDataURL(file);
  }

  uploadFile(): void {
    const row = this.order();
    const file = this.pendingFile();
    if (!row || !file) {
      return;
    }
    this.busy.set(true);
    this.onboarding.fulfillWithFile(row.id, file).subscribe({
      next: (next) => {
        this.order.set(next);
        this.pendingFile.set(null);
        this.busy.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.busy.set(false);
      },
    });
  }

  sendOtp(): void {
    const row = this.order();
    if (!row) {
      return;
    }
    this.busy.set(true);
    this.onboarding.requestFileOtp(row.id).subscribe({
      next: () => {
        this.otpSent.set(true);
        this.busy.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.busy.set(false);
      },
    });
  }

  reveal(): void {
    const row = this.order();
    if (!row) {
      return;
    }
    this.busy.set(true);
    this.onboarding.revealFilePassword(row.id, this.otpCtrl.value).subscribe({
      next: (payload) => {
        this.revealed.set(true);
        this.revealedPassword.set(payload.password);
        this.realFile = payload.file;
        this.busy.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.busy.set(false);
      },
    });
  }

  downloadReal(): void {
    if (!this.realFile) {
      return;
    }
    downloadDataUrl(this.realFile.fileName, this.realFile.dataUrl);
  }

  private realFile: FulfilmentFile | null = null;

  cancel(): void {
    const row = this.order();
    if (!row) {
      return;
    }
    this.busy.set(true);
    this.onboarding.cancelOrder(row.id).subscribe({
      next: (next) => {
        this.order.set(next);
        this.busy.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.busy.set(false);
      },
    });
  }

  setStatus(status: 'processing' | 'fulfilled' | 'cancelled'): void {
    const row = this.order();
    if (!row) {
      return;
    }
    this.busy.set(true);
    this.onboarding.adminSetOrderStatus(row.id, status).subscribe({
      next: (next) => {
        this.order.set(next);
        this.busy.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.busy.set(false);
      },
    });
  }

  private load(id: string): void {
    this.error.set('');
    this.order.set(null);
    this.onboarding.getOrder(id).subscribe({
      next: (row) => this.order.set(row),
      error: (err: Error) => this.error.set(err.message),
    });
  }
}
