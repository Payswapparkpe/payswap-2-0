import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-inline-alert',
  standalone: true,
  template: ` <p class="alert" [class.ok]="tone === 'success'" [class.info]="tone === 'info'" role="alert">{{ message }}</p> `,
  styles: [
    `
      .alert {
        margin: 0;
        border-radius: var(--ps-radius-sm);
        padding: 8px 10px;
        border: 1px solid #f9d7d5;
        background: #fff2f1;
        color: #b42318;
        font-size: 13px;
      }
      .ok {
        border-color: #b6e3c5;
        background: #ecf9f0;
        color: #0f7a3d;
      }
      .info {
        border-color: #d8e5ff;
        background: #f3f7ff;
        color: #1544ce;
      }
    `,
  ],
})
export class InlineAlertComponent {
  @Input({ required: true }) message = '';
  @Input() tone: 'error' | 'success' | 'info' = 'error';
}
