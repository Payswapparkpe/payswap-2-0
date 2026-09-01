import { Component } from '@angular/core';
import { CatalogOrderComponent } from './catalog-order.component';

@Component({
  selector: 'app-cards',
  standalone: true,
  imports: [CatalogOrderComponent],
  template: `<app-catalog-order kind="prepaid_card" />`,
})
export class CardsComponent {}
