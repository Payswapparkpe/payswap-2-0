import { DatePipe, TitleCasePipe } from '@angular/common';
import { Component, computed, inject, OnInit } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { OnboardingService } from '../../../core/services/onboarding.service';
import { AuthService } from '../../../core/services/auth.service';
import {
  agreementDone,
  isLive,
  kybApproved,
  kycDone,
  partnerSigned,
  PARTNER_TYPE_LABELS,
} from '../../../core/models/onboarding.models';
import { TestModeNoteComponent } from '../../../shared/ui/test-mode-note/test-mode-note.component';
import { LocaleService } from '../../../core/services/locale.service';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, MatButtonModule, DatePipe, TitleCasePipe, TestModeNoteComponent],
  template: `
    <app-test-mode-note
      [live]="live()"
      [message]="bannerMessage()"
      [cta]="bannerCta()"
      [link]="bannerLink()"
    />

    <div class="kpis">
      <article>
        <p>Open orders</p>
        <strong>{{ openCount() }}</strong>
        <span>Placed / processing</span>
      </article>
      <article>
        <p>Order value (30d)</p>
        <strong>{{ locale.formatCurrency(volume()) }}</strong>
        <span>{{ role() }}</span>
      </article>
      <article>
        <p>Fulfilled</p>
        <strong>{{ fulfilledCount() }}</strong>
        <span>Codes / cards delivered</span>
      </article>
      <article>
        <p>Partner status</p>
        <strong class="sm">{{ live() ? 'Live' : 'Activating' }}</strong>
        <span>{{ live() ? 'Ordering unlocked' : 'Complete activation' }}</span>
      </article>
    </div>

    <div class="grid">
      <article class="wide">
        <header>
          <h3>Recent orders</h3>
          <a routerLink="/app/orders">All orders</a>
        </header>
        <table>
          <thead>
            <tr>
              <th>Order</th>
              <th>Product</th>
              <th>Qty</th>
              <th>Amount</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            @for (row of recent(); track row.id) {
              <tr tabindex="0" (click)="open(row.id)" (keydown.enter)="open(row.id)" (keydown.space)="open(row.id)">
                <td>
                  <a [routerLink]="['/app/orders', row.id]" (click)="$event.stopPropagation()"><code>{{ row.id }}</code></a>
                  <small>{{ row.createdAt | date: 'short' }}</small>
                </td>
                <td>{{ row.title }} · {{ row.brand }}</td>
                <td>{{ row.quantity }}</td>
                <td>{{ locale.formatCurrency(row.amount) }}</td>
                <td>
                  <span class="mode" [class.test]="row.mode === 'test'">{{ row.mode === 'test' ? 'Test' : 'Live' }}</span>
                  {{ row.status | titlecase }}
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="5">No orders yet. Browse brand vouchers or prepaid cards.</td>
              </tr>
            }
          </tbody>
        </table>
      </article>

      <article>
        <header><h3>Quick order</h3></header>
        <div class="actions">
          <a routerLink="/app/vouchers">Brand vouchers</a>
          <a routerLink="/app/cards">Prepaid cards</a>
          <a routerLink="/app/account">KYC · KYB · Agreement</a>
        </div>
      </article>
    </div>
  `,
  styles: [
    `
      .kpis {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin-bottom: 14px;
      }
      .kpis article,
      .grid article {
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 16px;
        padding: 16px 18px;
      }
      .kpis p {
        margin: 0;
        font-size: 12px;
        color: #8a819d;
        font-weight: 650;
      }
      .kpis strong {
        display: block;
        margin: 8px 0 4px;
        font-size: 22px;
        letter-spacing: -0.04em;
      }
      .kpis strong.sm {
        font-size: 18px;
      }
      .kpis span {
        font-size: 12px;
        color: #6d6484;
      }
      .grid {
        display: grid;
        grid-template-columns: 1.7fr 1fr;
        gap: 14px;
      }
      .wide {
        grid-column: 1 / 2;
      }
      header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 10px;
      }
      h3 {
        margin: 0;
        font-size: 15px;
      }
      header a {
        font-size: 13px;
        font-weight: 700;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }
      th {
        text-align: left;
        color: #8a819d;
        font-size: 11px;
        text-transform: uppercase;
        padding: 8px 6px;
      }
      td {
        padding: 10px 6px;
        border-top: 1px solid #f0ebf7;
        vertical-align: top;
      }
      tbody tr {
        cursor: pointer;
      }
      tbody tr:hover {
        background: #faf8fd;
      }
      tbody tr:focus-visible {
        outline: 2px solid var(--ps-primary);
        outline-offset: -2px;
      }
      td small,
      code {
        display: block;
        color: #8a819d;
        font-size: 11px;
      }
      .mode {
        display: inline-block;
        margin-right: 6px;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        padding: 2px 7px;
        border-radius: 999px;
        background: #efe7ff;
        color: #5b21b6;
      }
      .mode.test {
        background: #fff4e8;
        color: #b45309;
      }
      .actions {
        display: grid;
        gap: 8px;
      }
      .actions a {
        padding: 10px 12px;
        border-radius: 10px;
        background: #f6f3fb;
        font-weight: 650;
        color: #13101c;
      }
      @media (max-width: 960px) {
        .kpis,
        .grid {
          grid-template-columns: 1fr;
        }
        .wide {
          grid-column: auto;
        }
      }
    `,
  ],
})
export class HomeComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly onboarding = inject(OnboardingService);
  private readonly router = inject(Router);
  readonly locale = inject(LocaleService);

  readonly live = computed(() => isLive(this.onboarding.application()));
  readonly recent = computed(() => this.onboarding.orders().slice(0, 5));
  readonly openCount = computed(
    () => this.onboarding.orders().filter((o) => o.status === 'placed' || o.status === 'processing').length,
  );
  readonly fulfilledCount = computed(
    () => this.onboarding.orders().filter((o) => o.status === 'fulfilled').length,
  );
  readonly volume = computed(() =>
    this.onboarding.orders().reduce((sum, o) => sum + o.amount, 0),
  );
  readonly role = computed(() => {
    const type = this.auth.user()?.partnerType;
    return type === 'corporate' ? PARTNER_TYPE_LABELS[type] : 'Partner';
  });

  ngOnInit(): void {
    this.onboarding.loadOrders().subscribe();
  }

  bannerMessage(): string {
    const app = this.onboarding.application();
    if (this.live()) {
      return '';
    }
    if (partnerSigned(app) && !agreementDone(app)) {
      return 'You signed the agreement. Payswap admin must countersign before live orders.';
    }
    if (kybApproved(app) && !partnerSigned(app)) {
      return 'KYC and KYB approved. Sign the partner agreement next.';
    }
    if (app?.status === 'under_review') {
      return 'Your KYC / KYB is with Payswap admin. Browse the catalog in test meanwhile.';
    }
    if (!kycDone(app)) {
      return 'Verify KYC first, then choose your business type to continue onboarding.';
    }
    if (!app?.profile.entityType) {
      return 'KYC is verified. Choose your business type next.';
    }
    return 'Finish entity KYB and the dual-signed agreement to place live orders.';
  }

  bannerCta(): string {
    const app = this.onboarding.application();
    if (this.live()) {
      return '';
    }
    if (kybApproved(app) && !partnerSigned(app)) {
      return 'Sign agreement';
    }
    return 'Open activation';
  }

  bannerLink(): string {
    const app = this.onboarding.application();
    if (kybApproved(app) && !partnerSigned(app)) {
      return '/app/agreement';
    }
    return '/app/account';
  }

  open(orderId: string): void {
    void this.router.navigate(['/app/orders', orderId]);
  }
}
