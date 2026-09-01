import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-empty-state',
  standalone: true,
  template: `
    <div class="empty">
      <h3>{{ title }}</h3>
      <p>{{ message }}</p>
    </div>
  `,
  styles: [
    `
      .empty {
        border: 1px dashed var(--ps-line);
        border-radius: var(--ps-radius-lg);
        padding: var(--ps-space-5);
        text-align: center;
        color: var(--ps-muted);
      }
      h3 {
        margin: 0 0 6px;
        font-size: 15px;
        color: var(--ps-ink);
      }
      p {
        margin: 0;
      }
    `,
  ],
})
export class EmptyStateComponent {
  @Input() title = 'Nothing yet';
  @Input() message = 'No data to show right now.';
}
