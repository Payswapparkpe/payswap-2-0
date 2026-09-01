import { DatePipe } from '@angular/common';
import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { OnboardingService } from '../../core/services/onboarding.service';

@Component({
  selector: 'app-admin-mail',
  standalone: true,
  imports: [DatePipe, RouterLink],
  template: `
    <article class="card">
      <table>
        <thead>
          <tr><th>Sent</th><th>To</th><th>Subject</th><th>Order</th></tr>
        </thead>
        <tbody>
          @for (row of onboarding.mail(); track row.id) {
            <tr>
              <td>{{ row.createdAt | date: 'short' }}</td>
              <td>{{ row.to }}</td>
              <td>{{ row.subject }}<div>{{ row.body }}</div></td>
              <td><a [routerLink]="['/admin/orders', row.orderId]">{{ row.orderId }}</a></td>
            </tr>
          } @empty {
            <tr><td colspan="4">No mock emails yet. Fulfil an order with a file to generate one.</td></tr>
          }
        </tbody>
      </table>
    </article>
  `,
  styles: [
    `
      .card { background: #fff; border: 1px solid #e7e1f2; border-radius: 16px; padding: 12px 16px; overflow: auto; }
      table { width: 100%; border-collapse: collapse; font-size: 13px; }
      th { text-align: left; font-size: 11px; text-transform: uppercase; color: #8a819d; padding: 8px; }
      td { padding: 10px 8px; border-top: 1px solid #f0ebf7; vertical-align: top; }
      td div { color: #8a819d; font-size: 12px; margin-top: 4px; max-width: 420px; }
    `,
  ],
})
export class AdminMailComponent implements OnInit {
  readonly onboarding = inject(OnboardingService);
  ngOnInit(): void {
    this.onboarding.loadMail().subscribe();
  }
}
