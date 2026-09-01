import { DatePipe, TitleCasePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { LogoComponent } from '../../shared/ui/logo/logo.component';
import { StatusChipComponent } from '../../shared/ui/status-chip/status-chip.component';
import { AuthService } from '../../core/services/auth.service';
import { OnboardingService } from '../../core/services/onboarding.service';
import { PARTNER_TYPE_LABELS } from '../../core/models/onboarding.models';
import { inr } from '../../core/config/commerce.data';
import { AppShellComponent } from '../../shared/ui/app-shell/app-shell.component';
import { NotificationService } from '../../core/services/notification.service';
import { LocaleService } from '../../core/services/locale.service';
import { TPipe } from '../../shared/pipes/t.pipe';

@Component({
  selector: 'app-admin-layout',
  standalone: true,
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatButtonModule,
    MatIconModule,
    LogoComponent,
    AppShellComponent,
    TPipe,
  ],
  template: `
    <app-shell
      role="Payswap admin"
      crumb="Admin"
      [heading]="heading"
      [userName]="auth.user()?.fullName || ''"
      [userMeta]="auth.user()?.email || ''"
    >
      <div shell-brand>
        <a routerLink="/admin" class="brand"><app-logo tone="light" [compact]="true" /></a>
      </div>
      <div shell-nav>
        <nav>
          <a routerLink="/admin" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">
            <mat-icon>dashboard</mat-icon> Overview
          </a>
          <a routerLink="/admin/partners" routerLinkActive="active">
            <mat-icon>groups</mat-icon> Partners
          </a>
          <a routerLink="/admin/orders" routerLinkActive="active">
            <mat-icon>shopping_bag</mat-icon> Orders
          </a>
          <a routerLink="/admin/leads" routerLinkActive="active">
            <mat-icon>handshake</mat-icon> Leads
          </a>
          <a routerLink="/admin/team" routerLinkActive="active">
            <mat-icon>badge</mat-icon> Team
          </a>
          <a routerLink="/admin/mail" routerLinkActive="active">
            <mat-icon>mail</mat-icon> Mail log
          </a>
        </nav>
      </div>
      <div shell-footer>
        <button mat-button type="button" class="logout" (click)="logout()">
          <mat-icon>logout</mat-icon> {{ 'signOut' | t }}
        </button>
      </div>
      <router-outlet />
    </app-shell>
  `,
  styles: [
    `
      .brand {
        padding: 4px 10px 8px;
      }
      .logout {
        margin-top: auto;
        color: #b7adc9;
        justify-content: flex-start;
      }
    `,
  ],
})
export class AdminLayoutComponent {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  heading = 'Overview';

  constructor() {
    this.router.events.subscribe(() => {
      const url = this.router.url;
      if (url.includes('/partners/')) this.heading = 'Partner file';
      else if (url.includes('/partners')) this.heading = 'Partners';
      else if (url.includes('/orders/')) this.heading = 'Order details';
      else if (url.includes('/orders')) this.heading = 'Orders';
      else if (url.includes('/leads/')) this.heading = 'Lead';
      else if (url.includes('/leads')) this.heading = 'Leads';
      else if (url.includes('/team')) this.heading = 'Team';
      else if (url.includes('/mail')) this.heading = 'Mail log';
      else this.heading = 'Overview';
    });
  }

  logout(): void {
    this.auth.logout().subscribe(() => void this.router.navigate(['/login']));
  }
}

@Component({
  selector: 'app-admin-home',
  standalone: true,
  imports: [RouterLink, MatButtonModule],
  template: `
    <div class="kpis">
      <article>
        <p>Awaiting KYC / KYB</p>
        <strong>{{ pendingKyc() }}</strong>
      </article>
      <article>
        <p>Awaiting admin sign</p>
        <strong>{{ pendingSign() }}</strong>
      </article>
      <article>
        <p>Live partners</p>
        <strong>{{ livePartners() }}</strong>
      </article>
      <article>
        <p>Open POs</p>
        <strong>{{ openOrders() }}</strong>
      </article>
      <article>
        <p>Files pending</p>
        <strong>{{ filesPending() }}</strong>
      </article>
      <article>
        <p>Open leads</p>
        <strong>{{ openLeads() }}</strong>
      </article>
    </div>
    <div class="actions">
      <a mat-flat-button color="primary" routerLink="/admin/partners">Review partners</a>
      <a mat-stroked-button routerLink="/admin/orders">Fulfil orders</a>
      <a mat-stroked-button routerLink="/admin/leads">Leads</a>
    </div>
  `,
  styles: [
    `
      .kpis {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 12px;
      }
      article {
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 16px;
        padding: 18px;
      }
      p {
        margin: 0;
        color: #8a819d;
        font-size: 12px;
        font-weight: 650;
      }
      strong {
        display: block;
        margin-top: 8px;
        font-size: 28px;
        letter-spacing: -0.04em;
      }
      .actions {
        display: flex;
        gap: 10px;
        margin-top: 16px;
      }
      @media (max-width: 900px) {
        .kpis {
          grid-template-columns: 1fr 1fr;
        }
      }
    `,
  ],
})
export class AdminHomeComponent implements OnInit {
  private readonly onboarding = inject(OnboardingService);
  readonly pendingKyc = computed(
    () => this.onboarding.partners().filter((p) => p.application?.status === 'under_review').length,
  );
  readonly pendingSign = computed(
    () =>
      this.onboarding.partners().filter((p) => p.application?.status === 'pending_admin_sign').length,
  );
  readonly livePartners = computed(
    () => this.onboarding.partners().filter((p) => p.application?.status === 'activated').length,
  );
  readonly openOrders = computed(
    () =>
      this.onboarding.orders().filter((o) => o.status === 'placed' || o.status === 'processing').length,
  );
  readonly filesPending = computed(
    () =>
      this.onboarding.orders().filter((o) => o.status === 'processing' && !o.fulfilmentFile).length,
  );
  readonly openLeads = computed(
    () => this.onboarding.leads().filter((l) => l.status !== 'won' && l.status !== 'lost').length,
  );

  ngOnInit(): void {
    this.onboarding.loadPartners().subscribe();
    this.onboarding.loadOrders().subscribe();
    this.onboarding.loadLeads().subscribe();
  }
}

@Component({
  selector: 'app-admin-partners',
  standalone: true,
  imports: [DatePipe, MatButtonModule, StatusChipComponent, RouterLink, FormsModule, MatFormFieldModule, MatInputModule],
  template: `
    <mat-form-field appearance="outline" class="search">
      <mat-label>Search partners</mat-label>
      <input matInput [ngModel]="query()" (ngModelChange)="query.set($event)" placeholder="Name, email, brand" />
    </mat-form-field>
    <div class="list">
      @for (row of filtered(); track row.user.id) {
        <article>
          <div class="top">
            <div>
              <h3>{{ row.application?.profile?.brandName || row.user.fullName }}</h3>
              <p>
                {{ typeLabel(row.user.partnerType) }} · {{ row.user.email }} ·
                {{ row.application?.profile?.legalName || '—' }}
              </p>
            </div>
            @if (row.application) {
              <app-status-chip [status]="row.application.status" />
            }
          </div>
          <dl>
            <div><dt>PAN</dt><dd>{{ row.application?.identity?.pan || '—' }}</dd></div>
            <div>
              <dt>Owners</dt>
              <dd>
                {{
                  row.application?.signatoryIsOwner === false
                    ? 'Signatory is not owner'
                    : row.application?.signatoryIsOwner
                      ? 'Signatory is owner'
                      : '—'
                }}
              </dd>
            </div>
            <div><dt>Signatory</dt><dd>{{ row.application?.signatory?.name || '—' }}</dd></div>
            <div>
              <dt>Submitted</dt>
              <dd>{{ row.application?.submittedAt ? (row.application?.submittedAt | date: 'medium') : '—' }}</dd>
            </div>
            <div>
              <dt>Partner signed</dt>
              <dd>{{ row.application?.agreement?.signedAt ? (row.application?.agreement?.signedAt | date: 'medium') : 'No' }}</dd>
            </div>
          </dl>
          <div class="actions">
            <a mat-stroked-button [routerLink]="['/admin/partners', row.user.id]">Open partner file</a>
          </div>
        </article>
      } @empty {
        <p>No partners yet.</p>
      }
    </div>
  `,
  styles: [
    `
      .search {
        width: min(420px, 100%);
        margin-bottom: 8px;
      }
      .list {
        display: grid;
        gap: 12px;
      }
      article {
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 16px;
        padding: 18px;
      }
      .top {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: start;
      }
      h3 {
        margin: 0 0 4px;
      }
      p {
        margin: 0;
        color: #6d6484;
      }
      dl {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
        margin: 14px 0;
      }
      dt {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #8a819d;
      }
      dd {
        margin: 4px 0 0;
        font-weight: 650;
      }
      .actions {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }
      .msg {
        color: #0f7a3d;
        font-weight: 650;
      }
      @media (max-width: 900px) {
        dl {
          grid-template-columns: 1fr 1fr;
        }
      }
    `,
  ],
})
export class AdminPartnersComponent implements OnInit {
  readonly onboarding = inject(OnboardingService);
  readonly query = signal('');
  readonly filtered = computed(() => {
    const q = this.query().trim().toLowerCase();
    return this.onboarding.partners().filter((row) => {
      if (!q) {
        return true;
      }
      const hay = `${row.user.fullName} ${row.user.email} ${row.application?.profile.brandName || ''} ${row.application?.profile.legalName || ''}`;
      return hay.toLowerCase().includes(q);
    });
  });

  ngOnInit(): void {
    this.onboarding.loadPartners().subscribe();
  }

  typeLabel(type: string): string {
    if (type === 'corporate') {
      return PARTNER_TYPE_LABELS[type];
    }
    return type;
  }
}

@Component({
  selector: 'app-admin-orders',
  standalone: true,
  imports: [DatePipe, TitleCasePipe, MatButtonModule, RouterLink],
  template: `
    <article class="card">
      <table>
        <thead>
          <tr>
            <th>Order</th>
            <th>PO</th>
            <th>Partner</th>
            <th>Product</th>
            <th>Amount</th>
            <th>Mode</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (row of onboarding.orders(); track row.id) {
            <tr>
              <td>
                <a [routerLink]="['/admin/orders', row.id]"><code>{{ row.id }}</code></a>
                <div>{{ row.createdAt | date: 'short' }}</div>
              </td>
              <td><code>{{ row.poNumber || '—' }}</code></td>
              <td>{{ partnerName(row.userId) }}</td>
              <td>{{ row.title }} · {{ row.brand }} × {{ row.quantity }}</td>
              <td>{{ locale.formatCurrency(row.amount) }}</td>
              <td>
                <span class="mode" [class.test]="row.mode === 'test'">{{ row.mode === 'test' ? 'Test' : 'Live' }}</span>
              </td>
              <td>{{ row.status | titlecase }}</td>
              <td class="acts">
                @if (row.status === 'placed') {
                  <button mat-stroked-button type="button" (click)="setStatus(row.id, 'processing')">Processing</button>
                }
                @if (row.status === 'placed' || row.status === 'processing') {
                  <button mat-stroked-button type="button" (click)="setStatus(row.id, 'fulfilled')">Fulfil</button>
                  <button mat-stroked-button color="warn" type="button" (click)="setStatus(row.id, 'cancelled')">Cancel</button>
                }
              </td>
            </tr>
          }
        </tbody>
      </table>
    </article>
  `,
  styles: [
    `
      .card {
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 16px;
        padding: 8px 16px 16px;
        overflow: auto;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }
      th,
      td {
        text-align: left;
        padding: 12px 8px;
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
      .acts {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .mode {
        display: inline-block;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        padding: 3px 8px;
        border-radius: 999px;
        background: #efe7ff;
        color: #5b21b6;
      }
      .mode.test {
        background: #fff4e8;
        color: #b45309;
      }
    `,
  ],
})
export class AdminOrdersComponent implements OnInit {
  readonly onboarding = inject(OnboardingService);
  readonly locale = inject(LocaleService);
  private readonly notify = inject(NotificationService);
  readonly inr = inr;

  ngOnInit(): void {
    this.onboarding.loadOrders().subscribe();
    this.onboarding.loadPartners().subscribe();
  }

  partnerName(userId: string): string {
    const hit = this.onboarding.partners().find((p) => p.user.id === userId);
    return hit?.application?.profile.brandName || hit?.user.fullName || userId.slice(0, 8);
  }

  setStatus(orderId: string, status: 'processing' | 'fulfilled' | 'cancelled'): void {
    this.onboarding.adminSetOrderStatus(orderId, status).subscribe({
      next: () => this.notify.success(`Order moved to ${status}.`),
      error: (err: Error) => this.notify.error(err.message),
    });
  }
}
