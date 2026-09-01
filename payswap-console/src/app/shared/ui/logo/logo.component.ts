import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-logo',
  standalone: true,
  template: `
    <span class="logo" [class.logo--compact]="compact">
      <img src="/branding/payswap-logo.png?v=2" alt="Payswap" />
    </span>
  `,
  styles: [
    `
      .logo {
        display: inline-flex;
        align-items: center;
        line-height: 0;
      }
      img {
        display: block;
        height: 40px;
        width: auto;
        max-width: 220px;
        object-fit: contain;
        object-position: left center;
      }
      .logo--compact img {
        height: 28px;
        max-width: 148px;
      }
    `,
  ],
})
export class LogoComponent {
  /** Kept so existing `tone` bindings still compile. The wordmark is the same on dark nav. */
  @Input() tone: 'dark' | 'light' = 'dark';
  @Input() compact = false;
}
