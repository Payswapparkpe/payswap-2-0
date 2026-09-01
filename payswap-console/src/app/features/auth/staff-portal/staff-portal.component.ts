import { RouterLink } from '@angular/router';
import { Component } from '@angular/core';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-staff-portal',
  standalone: true,
  imports: [RouterLink],
  template: `
    <main class="wrap">
      <p class="kicker">Staff &amp; admin access</p>
      <h1>Use the Payswap staff portal</h1>
      <p class="lead">
        KYC reviewers, operations, and platform admins sign in through Django — not this partner console.
      </p>
      <a class="btn" [href]="staffLoginUrl">Open staff sign-in</a>
      <p class="hint">Corporate partners should use <a routerLink="/login">partner sign-in</a>.</p>
    </main>
  `,
  styles: [
    `
      .wrap {
        min-height: 100vh;
        display: grid;
        place-content: center;
        padding: 24px;
        text-align: center;
        gap: 12px;
      }
      .kicker {
        margin: 0;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #7a3dff;
      }
      h1 {
        margin: 0;
        font-size: clamp(28px, 4vw, 40px);
        letter-spacing: -0.04em;
      }
      .lead,
      .hint {
        color: #6d6484;
        max-width: 520px;
      }
      .btn {
        display: inline-block;
        margin-top: 8px;
        padding: 12px 20px;
        border-radius: 999px;
        background: linear-gradient(90deg, #1b4dfe, #ac24ff);
        color: #fff;
        font-weight: 700;
        text-decoration: none;
      }
    `,
  ],
})
export class StaffPortalComponent {
  readonly staffLoginUrl = environment.staffLoginUrl;
}
