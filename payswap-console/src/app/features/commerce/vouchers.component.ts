import { Component } from '@angular/core';
import { CatalogOrderComponent } from './catalog-order.component';

@Component({
  selector: 'app-vouchers',
  standalone: true,
  imports: [CatalogOrderComponent],
  template: `<app-catalog-order kind="brand_voucher" />`,
})
export class VouchersComponent {}
