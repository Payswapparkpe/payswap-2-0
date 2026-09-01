import { CurrencyPipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { BRAND_CATALOG, inr } from '../../core/config/commerce.data';
import { CatalogItem } from '../../core/models/onboarding.models';
import { OnboardingService } from '../../core/services/onboarding.service';
import { WorkspaceModeService } from '../../core/services/workspace-mode.service';

@Component({
  selector: 'app-create-po',
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, CurrencyPipe],
  template: `
    <article class="card">
      <h2>Create purchase order</h2>
      <p class="sub">Every voucher or prepaid load needs a PO number before Payswap can fulfil.</p>
      <div class="grid">
        <mat-form-field appearance="outline">
          <mat-label>Product</mat-label>
          <mat-select [ngModel]="itemId()" (ngModelChange)="pick($event)">
            @for (item of catalog; track item.id) {
              <mat-option [value]="item.id">{{ item.brand }} · {{ item.title }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        @if (item(); as sku) {
          <mat-form-field appearance="outline">
            <mat-label>Denomination</mat-label>
            <mat-select [(ngModel)]="unitValue">
              @for (d of sku.denominations; track d) {
                <mat-option [value]="d">{{ d | currency: 'INR' : 'symbol' : '1.0-0' }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
        }
        <mat-form-field appearance="outline">
          <mat-label>Quantity</mat-label>
          <input matInput type="number" min="1" [(ngModel)]="quantity" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>PO number</mat-label>
          <input matInput [(ngModel)]="poNumber" placeholder="PO-ACME-2401" />
        </mat-form-field>
        <mat-form-field appearance="outline" class="wide">
          <mat-label>Note</mat-label>
          <input matInput [(ngModel)]="note" />
        </mat-form-field>
      </div>
      <p class="total">{{ inr(quantity * unitValue) }}</p>
      @if (error()) {
        <p class="error">{{ error() }}</p>
      }
      <button mat-flat-button color="primary" type="button" [disabled]="busy()" (click)="submit()">
        {{ busy() ? 'Submitting…' : 'Submit PO' }}
      </button>
    </article>
  `,
  styles: [
    `
      .card {
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 16px;
        padding: 20px;
        max-width: 720px;
      }
      h2 {
        margin: 0 0 6px;
      }
      .sub {
        color: #6d6484;
        margin: 0 0 16px;
      }
      .grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
      }
      .wide {
        grid-column: 1 / -1;
      }
      .total {
        font-weight: 800;
      }
      .error {
        color: #b42318;
      }
      @media (max-width: 700px) {
        .grid {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class CreatePoComponent {
  private readonly onboarding = inject(OnboardingService);
  private readonly workspace = inject(WorkspaceModeService);
  private readonly router = inject(Router);
  readonly catalog = BRAND_CATALOG;
  readonly inr = inr;
  readonly itemId = signal(BRAND_CATALOG[0]?.id || '');
  readonly error = signal('');
  readonly busy = signal(false);
  quantity = 10;
  unitValue = BRAND_CATALOG[0]?.denominations[0] ?? 500;
  poNumber = '';
  note = '';

  item(): CatalogItem | undefined {
    return this.catalog.find((c) => c.id === this.itemId());
  }

  pick(id: string): void {
    this.itemId.set(id);
    const sku = this.catalog.find((c) => c.id === id);
    this.unitValue = sku?.denominations[1] ?? sku?.denominations[0] ?? 500;
  }

  submit(): void {
    const sku = this.item();
    if (!sku) {
      return;
    }
    if (!this.poNumber.trim()) {
      this.error.set('PO number is required.');
      return;
    }
    if (this.quantity < 1) {
      this.error.set('Enter a valid quantity.');
      return;
    }
    this.busy.set(true);
    this.error.set('');
    this.onboarding
      .placeOrder({
        kind: sku.kind,
        title: sku.title,
        brand: sku.brand,
        quantity: Number(this.quantity),
        unitValue: Number(this.unitValue),
        note: this.note,
        mode: this.workspace.mode(),
        poNumber: this.poNumber.trim(),
      })
      .subscribe({
        next: (order) => {
          this.busy.set(false);
          void this.router.navigate(['/app/orders', order.id]);
        },
        error: (err: Error) => {
          this.busy.set(false);
          this.error.set(err.message);
        },
      });
  }
}
