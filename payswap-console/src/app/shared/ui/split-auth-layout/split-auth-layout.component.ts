import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LogoComponent } from '../logo/logo.component';

@Component({
  selector: 'app-split-auth-layout',
  standalone: true,
  imports: [RouterLink, LogoComponent],
  template: `
    <div class="auth-shell">
      <aside class="brand">
        <a routerLink="/login" class="brand-logo"><app-logo /></a>
        <div class="brand-copy">
          <p class="eyebrow">Prepaid cards & brand vouchers</p>
          <h1>Brand vouchers and prepaid cards in one console.</h1>
          <p class="lede">
            Corporates order brand vouchers and prepaid cards. Complete Indian KYC first, then KYB
            for your entity type, then dual-sign the partner agreement with Payswap admin.
          </p>
          <ul>
            <li>Prepaid meal and reward card loads</li>
            <li>Brand voucher catalog for employee and channel rewards</li>
            <li>Admin verifies partners and countersigns agreements</li>
          </ul>
        </div>
        <p class="footnote">Demo OTP is always <strong>123456</strong>. No live DigiLocker or registry APIs.</p>
      </aside>
      <main class="panel">
        <ng-content />
      </main>
    </div>
  `,
  styles: [
    `
      .auth-shell {
        min-height: 100vh;
        display: grid;
        grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
      }
      .brand {
        position: relative;
        overflow: hidden;
        padding: 32px 48px 28px;
        display: flex;
        flex-direction: column;
        color: #f8f7fb;
        background:
          radial-gradient(1200px 600px at -10% -20%, rgba(27, 77, 254, 0.45), transparent 55%),
          radial-gradient(900px 500px at 110% 10%, rgba(172, 36, 255, 0.38), transparent 50%),
          radial-gradient(700px 400px at 70% 110%, rgba(254, 136, 27, 0.22), transparent 45%),
          #0c0a14;
      }
      .brand::after {
        content: '';
        position: absolute;
        inset: 0;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)' opacity='.18'/%3E%3C/svg%3E");
        opacity: 0.18;
        pointer-events: none;
      }
      .brand-logo {
        position: relative;
        z-index: 1;
        width: fit-content;
        border-radius: 12px;
        transition: transform 140ms ease, opacity 140ms ease;
      }
      .brand-logo:hover {
        transform: translateY(-1px);
        opacity: 0.96;
      }
      .brand-copy {
        position: relative;
        z-index: 1;
        margin-top: auto;
        max-width: 520px;
        padding: 48px 0 32px;
      }
      .eyebrow {
        text-transform: uppercase;
        letter-spacing: 0.16em;
        font-size: 11px;
        font-weight: 700;
        color: #c86fff;
        margin: 0 0 14px;
      }
      h1 {
        font-size: clamp(32px, 4vw, 46px);
        line-height: 1.08;
        letter-spacing: -0.04em;
        margin: 0 0 16px;
      }
      .lede {
        color: #c9c1dd;
        line-height: 1.55;
        margin: 0 0 22px;
      }
      ul {
        margin: 0;
        padding: 0;
        list-style: none;
        display: grid;
        gap: 10px;
        color: #e8e4f4;
        font-size: 14px;
      }
      li::before {
        content: '';
        display: inline-block;
        width: 8px;
        height: 8px;
        margin-right: 10px;
        border-radius: 99px;
        background: linear-gradient(100deg, #1b4dfe, #ac24ff, #fe881b);
      }
      .footnote {
        position: relative;
        z-index: 1;
        margin: 0;
        color: #83799e;
        font-size: 12px;
      }
      .panel {
        background: var(--ps-paper);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 40px 28px;
      }
      @media (max-width: 900px) {
        .auth-shell {
          grid-template-columns: 1fr;
        }
        .brand {
          min-height: auto;
          padding: 24px 22px 18px;
        }
        .brand-copy {
          padding: 20px 0 12px;
        }
        h1 {
          font-size: 28px;
        }
        ul {
          display: none;
        }
      }
    `,
  ],
})
export class SplitAuthLayoutComponent {}
