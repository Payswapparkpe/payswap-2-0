import { Component, Input } from '@angular/core';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

@Component({
  selector: 'app-loading-state',
  standalone: true,
  imports: [MatProgressSpinnerModule],
  template: `
    <div class="loading" [attr.aria-label]="label">
      <mat-spinner diameter="20"></mat-spinner>
      <span>{{ label }}</span>
    </div>
  `,
  styles: [
    `
      .loading {
        min-height: 110px;
        display: inline-flex;
        align-items: center;
        gap: 10px;
        color: var(--ps-muted);
        font-size: 13px;
      }
    `,
  ],
})
export class LoadingStateComponent {
  @Input() label = 'Loading...';
}
