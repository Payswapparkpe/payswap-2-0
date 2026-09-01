import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-test-mode-note',
  standalone: true,
  imports: [RouterLink],
  template: `
    @if (!live) {
      <aside class="note">
        <strong>Test mode.</strong>
        {{ message }}
        @if (cta) {
          <a [routerLink]="link">{{ cta }}</a>
        }
      </aside>
    }
  `,
  styles: [
    `
      .note {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: baseline;
        padding: 10px 14px;
        border-radius: 12px;
        background: #eef3ff;
        color: #24356b;
        font-size: 13px;
        margin-bottom: 16px;
      }
      a {
        font-weight: 700;
      }
    `,
  ],
})
export class TestModeNoteComponent {
  @Input() live = false;
  @Input() message = 'Figures below are sandbox traffic until the account is live.';
  @Input() cta = '';
  @Input() link = '/app/account';
}
