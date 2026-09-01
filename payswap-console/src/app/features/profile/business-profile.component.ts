import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { OnboardingService } from '../../core/services/onboarding.service';
import { ENTITY_LABELS, isApplicationEditable } from '../../core/models/onboarding.models';
import { BUSINESS_CATEGORIES, MONTHLY_VOLUMES } from '../../core/config/business-categories';

@Component({
  selector: 'app-business-profile',
  standalone: true,
  imports: [RouterLink, MatButtonModule],
  template: `
    @if (onboarding.application(); as app) {
      <article class="card">
        <header>
          <h3>Submitted business details</h3>
          @if (editable()) {
            <a mat-stroked-button routerLink="/app/onboarding">Edit in wizard</a>
          }
        </header>
        <dl>
          <div><dt>Brand</dt><dd>{{ app.profile.brandName || '—' }}</dd></div>
          <div><dt>Legal name</dt><dd>{{ app.profile.legalName || '—' }}</dd></div>
          <div><dt>Entity</dt><dd>{{ app.profile.entityType ? labels[app.profile.entityType] : '—' }}</dd></div>
          <div>
            <dt>Signatory / owner</dt>
            <dd>
              {{
                app.signatoryIsOwner === false
                  ? 'Authorised signatory only — owner KYC required'
                  : app.signatoryIsOwner
                    ? 'Signatory is also a director / owner'
                    : '—'
              }}
            </dd>
          </div>
          <div><dt>Category</dt><dd>{{ categoryLabel(app.profile.category) }}</dd></div>
          <div><dt>Website</dt><dd>{{ app.profile.website || '—' }}</dd></div>
          <div><dt>Volume</dt><dd>{{ volumeLabel(app.profile.monthlyVolume) }}</dd></div>
          <div><dt>GSTIN</dt><dd>{{ app.profile.noGstin ? 'Declared — no GSTIN' : app.profile.gstin || '—' }}</dd></div>
          <div><dt>PAN</dt><dd>{{ app.identity.pan || '—' }}</dd></div>
          <div><dt>CIN / LLPIN</dt><dd>{{ app.identity.cin || app.identity.llpin || '—' }}</dd></div>
          <div>
            <dt>Registered office</dt>
            <dd>{{ formatAddress(app.identity.registeredAddress) }}</dd>
          </div>
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
        gap: 12px;
        align-items: center;
      }
      dl {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
        margin: 18px 0 0;
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
      @media (max-width: 700px) {
        dl {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class BusinessProfileComponent {
  readonly onboarding = inject(OnboardingService);
  readonly labels = ENTITY_LABELS;
  readonly editable = computed(() => isApplicationEditable(this.onboarding.application()));

  categoryLabel(category: string): string {
    return BUSINESS_CATEGORIES.find((c) => c.id === category)?.label || '—';
  }

  volumeLabel(id: string): string {
    return MONTHLY_VOLUMES.find((v) => v.id === id)?.label ?? '—';
  }

  formatAddress(address: { line1: string; city: string; state: string; pin: string }): string {
    const parts = [address.line1, address.city, address.state, address.pin].filter(Boolean);
    return parts.join(', ') || '—';
  }
}
