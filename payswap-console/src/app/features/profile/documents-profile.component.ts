import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { OnboardingService } from '../../core/services/onboarding.service';
import { documentsFor } from '../../core/config/entity-documents';
import { isApplicationEditable } from '../../core/models/onboarding.models';

@Component({
  selector: 'app-documents-profile',
  standalone: true,
  imports: [RouterLink, MatButtonModule],
  template: `
    @if (onboarding.application(); as app) {
      <article class="card">
        <header>
          <h3>Uploaded files</h3>
          @if (editable()) {
            <a mat-stroked-button routerLink="/app/onboarding">Manage in wizard</a>
          }
        </header>
        <ul>
          @for (slot of slots(); track slot.id) {
            <li>
              <div>
                <strong>{{ slot.label }}</strong>
                <span>{{ fileName(slot.id) }}</span>
              </div>
              <em>{{ fileName(slot.id) === 'Not uploaded' ? 'Missing' : 'Received' }}</em>
            </li>
          } @empty {
            <li>Select an entity type in onboarding to see required documents.</li>
          }
        </ul>
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
      }
      ul {
        list-style: none;
        padding: 0;
        margin: 16px 0 0;
        display: grid;
        gap: 10px;
      }
      li {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 0;
        border-bottom: 1px solid #efeaf8;
      }
      span,
      em {
        display: block;
        color: #6d6484;
        font-size: 13px;
        font-style: normal;
      }
    `,
  ],
})
export class DocumentsProfileComponent {
  readonly onboarding = inject(OnboardingService);
  readonly editable = computed(() => isApplicationEditable(this.onboarding.application()));
  readonly slots = computed(() => {
    const app = this.onboarding.application();
    if (!app) {
      return [];
    }
    return documentsFor(app.profile.entityType, app.profile.category, app.signatory.verified);
  });

  fileName(slotId: string): string {
    return this.onboarding.application()?.documents.find((d) => d.slotId === slotId)?.fileName ?? 'Not uploaded';
  }
}
