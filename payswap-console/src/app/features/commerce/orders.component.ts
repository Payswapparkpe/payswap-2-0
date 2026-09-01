import { DatePipe, TitleCasePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { OnboardingService } from '../../core/services/onboarding.service';
import { isLive, OrderKind, OrderStatus } from '../../core/models/onboarding.models';
import { kindLabel } from '../../core/config/order.util';
import { TestModeNoteComponent } from '../../shared/ui/test-mode-note/test-mode-note.component';
import { LocaleService } from '../../core/services/locale.service';

@Component({
  selector: 'app-orders',
  standalone: true,
  imports: [
    DatePipe,
    TitleCasePipe,
    FormsModule,
    RouterLink,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    TestModeNoteComponent,
  ],
  template: `
    <app-test-mode-note
      [live]="live"
      message="Orders placed before activation stay in the sandbox queue."
    />
    <article class="card">
      <div class="filters">
        <mat-form-field appearance="outline">
          <mat-label>Search</mat-label>
          <input matInput [ngModel]="query()" (ngModelChange)="query.set($event)" placeholder="Order id or brand" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Status</mat-label>
          <mat-select [ngModel]="status()" (ngModelChange)="status.set($event)">
            <mat-option value="all">All statuses</mat-option>
            <mat-option value="placed">Placed</mat-option>
            <mat-option value="processing">Processing</mat-option>
            <mat-option value="fulfilled">Fulfilled</mat-option>
            <mat-option value="cancelled">Cancelled</mat-option>
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Type</mat-label>
          <mat-select [ngModel]="kind()" (ngModelChange)="kind.set($event)">
            <mat-option value="all">All types</mat-option>
            <mat-option value="brand_voucher">Brand voucher</mat-option>
            <mat-option value="prepaid_card">Prepaid card</mat-option>
            <mat-option value="corporate_gifting">Gifting (legacy)</mat-option>
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>From date</mat-label>
          <input matInput type="date" [ngModel]="fromDate()" (ngModelChange)="fromDate.set($event)" />
        </mat-form-field>
      </div>
      <table>
        <thead>
          <tr>
            <th>Order</th>
            <th>PO</th>
            <th>Type</th>
            <th>Product</th>
            <th>Qty</th>
            <th>Amount</th>
            <th>Mode</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          @for (row of filtered(); track row.id) {
            <tr tabindex="0" (click)="open(row.id)" (keydown.enter)="open(row.id)" (keydown.space)="open(row.id)">
              <td>
                <a [routerLink]="['/app/orders', row.id]" (click)="$event.stopPropagation()"><code>{{ row.id }}</code></a>
                <div>{{ row.createdAt | date: 'short' }}</div>
              </td>
              <td><code>{{ row.poNumber || '—' }}</code></td>
              <td>{{ label(row.kind) }}</td>
              <td>{{ row.title }} · {{ row.brand }}</td>
              <td>{{ row.quantity }} × {{ locale.formatCurrency(row.unitValue) }}</td>
              <td>{{ locale.formatCurrency(row.amount) }}</td>
              <td>
                <span class="mode" [class.test]="row.mode === 'test'">{{ row.mode === 'test' ? 'Test' : 'Live' }}</span>
              </td>
              <td>{{ row.status | titlecase }}</td>
            </tr>
          } @empty {
            <tr>
              <td colspan="8">No orders match these filters.</td>
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
      .filters {
        display: grid;
        grid-template-columns: 1.4fr repeat(3, 1fr);
        gap: 8px;
        padding-top: 12px;
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
      code,
      td div {
        color: #8a819d;
        font-size: 12px;
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
      @media (max-width: 900px) {
        .filters {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class OrdersComponent implements OnInit {
  readonly onboarding = inject(OnboardingService);
  readonly locale = inject(LocaleService);
  private readonly router = inject(Router);
  readonly query = signal('');
  readonly status = signal<'all' | OrderStatus>('all');
  readonly kind = signal<'all' | OrderKind>('all');
  readonly fromDate = signal('');
  readonly filtered = computed(() => {
    const q = this.query().trim().toLowerCase();
    const status = this.status();
    const kind = this.kind();
    const from = this.fromDate();
    return this.onboarding.orders().filter((row) => {
      if (status !== 'all' && row.status !== status) {
        return false;
      }
      if (kind !== 'all' && row.kind !== kind) {
        return false;
      }
      if (from && row.createdAt.slice(0, 10) < from) {
        return false;
      }
      if (!q) {
        return true;
      }
      return `${row.id} ${row.brand} ${row.title} ${row.poNumber}`.toLowerCase().includes(q);
    });
  });

  get live(): boolean {
    return isLive(this.onboarding.application());
  }

  ngOnInit(): void {
    this.onboarding.loadOrders().subscribe();
  }

  label(kind: string): string {
    return kindLabel(kind);
  }

  open(orderId: string): void {
    void this.router.navigate(['/app/orders', orderId]);
  }
}
