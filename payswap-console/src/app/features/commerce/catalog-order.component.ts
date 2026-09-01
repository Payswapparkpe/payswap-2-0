import { CurrencyPipe } from '@angular/common';
import { Component, Input, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { BRAND_CATALOG, VOUCHER_CATEGORIES, inr } from '../../core/config/commerce.data';
import { CatalogItem, OrderKind, isLive } from '../../core/models/onboarding.models';
import { OnboardingService } from '../../core/services/onboarding.service';
import { WorkspaceModeService } from '../../core/services/workspace-mode.service';
import { TestModeNoteComponent } from '../../shared/ui/test-mode-note/test-mode-note.component';

@Component({
  selector: 'app-catalog-order',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    CurrencyPipe,
    TestModeNoteComponent,
  ],
  template: `
    <app-test-mode-note
      [live]="live()"
      message="Catalog is browsable now. Live fulfilment needs KYC, KYB and dual agreement."
      cta="Activation"
      link="/app/account"
    />

    @if (kind === 'brand_voucher') {
      <div class="voucher-layout">
        <div>
          <div class="filters">
            @for (cat of categories; track cat) {
              <button type="button" class="chip" [class.on]="filter() === cat" (click)="filter.set(cat)">
                {{ cat }}
              </button>
            }
          </div>
          <div class="catalog">
            @for (item of visibleItems(); track item.id) {
              <button type="button" class="brand-tile" [class.picked]="selected()?.id === item.id" (click)="pick(item)">
                <span class="mark" [style.background]="item.accent + '18'">
                  <img [src]="item.logo" [alt]="item.brand" />
                </span>
                <strong>{{ item.brand }}</strong>
                <small>{{ item.category }}</small>
              </button>
            }
          </div>
        </div>

        <aside class="order-panel">
          @if (selected(); as item) {
            <img class="hero-logo" [src]="item.logo" [alt]="item.brand" />
            <p class="eyebrow">{{ item.category }}</p>
            <h3>{{ item.title }}</h3>
            <p class="hint">Choose a denomination and quantity, then place the order.</p>
            <mat-form-field appearance="outline">
              <mat-label>Denomination</mat-label>
              <mat-select [(ngModel)]="draft[item.id].unitValue">
                @for (d of item.denominations; track d) {
                  <mat-option [value]="d">{{ d | currency: 'INR' : 'symbol' : '1.0-0' }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Quantity</mat-label>
              <input matInput type="number" min="1" [(ngModel)]="draft[item.id].quantity" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>PO number</mat-label>
              <input matInput [(ngModel)]="draft[item.id].poNumber" placeholder="PO-ACME-2401" />
            </mat-form-field>
            <p class="total">{{ inr(draft[item.id].quantity * draft[item.id].unitValue) }}</p>
            <button mat-flat-button color="primary" type="button" (click)="order(item)" [disabled]="busy() === item.id">
              {{ busy() === item.id ? 'Placing…' : live() ? 'Place order' : 'Place test order' }}
            </button>
          } @else {
            <p class="empty">Select a brand from the catalog to place an order.</p>
          }
          @if (error()) {
            <p class="error">{{ error() }}</p>
          }
          @if (ok(); as message) {
            <p class="ok">{{ message }} <a [routerLink]="['/app/orders', lastId()]">View order</a></p>
          }
        </aside>
      </div>
    } @else {
      <div class="grid">
        @for (item of items; track item.id) {
          <article>
            <div class="card-head">
              <img [src]="item.logo" [alt]="item.brand" />
              <div>
                <p class="brand">{{ item.brand }} · {{ item.category }}</p>
                <h3>{{ item.title }}</h3>
              </div>
            </div>
            <div class="row">
              <mat-form-field appearance="outline">
                <mat-label>Denomination</mat-label>
                <mat-select [(ngModel)]="draft[item.id].unitValue">
                  @for (d of item.denominations; track d) {
                    <mat-option [value]="d">{{ d | currency: 'INR' : 'symbol' : '1.0-0' }}</mat-option>
                  }
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Quantity</mat-label>
                <input matInput type="number" min="1" [(ngModel)]="draft[item.id].quantity" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>PO number</mat-label>
                <input matInput [(ngModel)]="draft[item.id].poNumber" placeholder="PO-ACME-2401" />
              </mat-form-field>
            </div>
            <p class="total">{{ inr(draft[item.id].quantity * draft[item.id].unitValue) }}</p>
            <button mat-flat-button color="primary" type="button" (click)="order(item)" [disabled]="busy() === item.id">
              {{ busy() === item.id ? 'Placing…' : live() ? 'Place order' : 'Place test order' }}
            </button>
          </article>
        }
      </div>
      @if (error()) {
        <p class="error">{{ error() }}</p>
      }
      @if (ok(); as message) {
        <p class="ok">{{ message }} <a [routerLink]="['/app/orders', lastId()]">View order</a></p>
      }
    }
  `,
  styles: [
    `
      .voucher-layout {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 320px;
        gap: 16px;
        align-items: start;
      }
      .filters {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 12px;
      }
      .chip {
        border: 1px solid #e7e1f2;
        background: #fff;
        border-radius: 999px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 650;
        cursor: pointer;
      }
      .chip.on {
        background: #5b3df5;
        color: #fff;
        border-color: #5b3df5;
      }
      .catalog {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 10px;
      }
      .brand-tile {
        display: grid;
        justify-items: center;
        gap: 6px;
        width: 100%;
        border: 1px solid #e7e1f2;
        background: #fff;
        border-radius: 16px;
        padding: 14px 8px 12px;
        cursor: pointer;
        text-align: center;
        font: inherit;
        color: inherit;
      }
      .brand-tile.picked {
        border-color: #5b3df5;
        box-shadow: 0 0 0 3px #5b3df522;
      }
      .mark {
        width: 56px;
        height: 56px;
        border-radius: 14px;
        display: grid;
        place-items: center;
      }
      .mark img,
      .hero-logo,
      .card-head img {
        width: 56px;
        height: 56px;
        border-radius: 14px;
      }
      .brand-tile strong {
        font-size: 13px;
      }
      .brand-tile small {
        color: #8a819d;
        font-size: 11px;
      }
      .order-panel {
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 16px;
        padding: 18px;
        position: sticky;
        top: 12px;
      }
      .hero-logo {
        margin-bottom: 8px;
      }
      .eyebrow {
        margin: 0;
        font-size: 11px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #8a819d;
        font-weight: 700;
      }
      .hint,
      .empty {
        color: #6d6484;
        font-size: 13px;
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 14px;
      }
      article {
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 16px;
        padding: 18px;
      }
      .card-head {
        display: flex;
        gap: 12px;
        align-items: center;
        margin-bottom: 8px;
      }
      .brand {
        margin: 0;
        font-size: 11px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #8a819d;
        font-weight: 700;
      }
      h3 {
        margin: 6px 0 12px;
      }
      .row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
      }
      .total {
        font-weight: 800;
        font-size: 18px;
        letter-spacing: -0.03em;
      }
      .error {
        color: #b42318;
      }
      .ok {
        color: #0f7a3d;
        font-weight: 650;
      }
      .order-panel mat-form-field {
        width: 100%;
      }
      @media (max-width: 960px) {
        .voucher-layout,
        .catalog,
        .grid {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class CatalogOrderComponent {
  @Input({ required: true }) kind!: OrderKind;

  private readonly onboarding = inject(OnboardingService);
  private readonly workspace = inject(WorkspaceModeService);
  readonly inr = inr;
  readonly categories = VOUCHER_CATEGORIES;
  readonly filter = signal('All');
  readonly selected = signal<CatalogItem | null>(null);
  readonly busy = signal('');
  readonly error = signal('');
  readonly ok = signal('');
  readonly lastId = signal('');
  draft: Record<string, { quantity: number; unitValue: number; poNumber: string }> = {};

  get items(): CatalogItem[] {
    return BRAND_CATALOG.filter((c) => c.kind === this.kind);
  }

  visibleItems(): CatalogItem[] {
    const cat = this.filter();
    return this.items.filter((item) => cat === 'All' || item.category === cat);
  }

  live(): boolean {
    return isLive(this.onboarding.application());
  }

  constructor() {
    BRAND_CATALOG.forEach((item) => {
      this.draft[item.id] = { quantity: 10, unitValue: item.denominations[1] ?? item.denominations[0], poNumber: '' };
    });
  }

  pick(item: CatalogItem): void {
    this.selected.set(item);
    this.error.set('');
    this.ok.set('');
  }

  order(item: CatalogItem): void {
    const d = this.draft[item.id];
    if (!d.quantity || d.quantity < 1) {
      this.error.set('Enter a valid quantity.');
      return;
    }
    if (!d.poNumber.trim()) {
      this.error.set('Enter the purchase order number.');
      return;
    }
    this.error.set('');
    this.ok.set('');
    this.busy.set(item.id);
    this.onboarding
      .placeOrder({
        kind: item.kind,
        title: item.title,
        brand: item.brand,
        quantity: Number(d.quantity),
        unitValue: Number(d.unitValue),
        note: '',
        mode: this.workspace.mode(),
        poNumber: d.poNumber.trim(),
      })
      .subscribe({
        next: (order) => {
          this.busy.set('');
          this.lastId.set(order.id);
          this.ok.set(`Order ${order.id} placed.`);
        },
        error: (err: Error) => {
          this.busy.set('');
          this.error.set(err.message);
        },
      });
  }
}
