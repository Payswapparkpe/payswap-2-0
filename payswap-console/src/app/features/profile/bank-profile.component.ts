import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { OnboardingService } from '../../core/services/onboarding.service';
import { isApplicationEditable } from '../../core/models/onboarding.models';

@Component({
  selector: 'app-bank-profile',
  standalone: true,
  imports: [RouterLink, MatButtonModule],
  template: `
    @if (onboarding.application(); as app) {
      <article class="card">
        <header>
          <h3>Settlement account</h3>
          @if (editable()) {
            <a mat-stroked-button routerLink="/app/onboarding">Update in wizard</a>
          }
        </header>
        <p class="warn">Bank account name, PAN name, and GST legal name must match exactly.</p>
        <dl>
          <div><dt>Holder</dt><dd>{{ app.bank.holderName || '—' }}</dd></div>
          <div><dt>Account</dt><dd>{{ app.bank.accountNumber || '—' }}</dd></div>
          <div><dt>IFSC</dt><dd>{{ app.bank.ifsc || '—' }}</dd></div>
          <div><dt>Bank</dt><dd>{{ app.bank.bankName || '—' }} {{ app.bank.branch ? '· ' + app.bank.branch : '' }}</dd></div>
          <div><dt>Type</dt><dd>{{ app.bank.accountType }}</dd></div>
          <div><dt>Penny drop</dt><dd>{{ app.bank.pennyDropStatus }}</dd></div>
        </dl>
      </article>
    }
  `,
  styles: [
    `
      .card {
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 18px;
        padding: 22px;
      }
      header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
      }
      .warn {
        color: #9a4b00;
        background: #fff4e5;
        padding: 10px 12px;
        border-radius: 10px;
      }
      dl {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
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
    `,
  ],
})
export class BankProfileComponent {
  readonly onboarding = inject(OnboardingService);
  readonly editable = computed(() => isApplicationEditable(this.onboarding.application()));
}
