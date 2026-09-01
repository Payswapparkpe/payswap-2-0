import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { DigilockerSessionService } from '../../../core/services/digilocker-session.service';

@Component({
  selector: 'app-digilocker-overlay',
  standalone: true,
  imports: [MatButtonModule],
  template: `
    @if (session.active()) {
      <div class="backdrop" role="dialog" aria-modal="true" aria-label="DigiLocker verification">
        <section class="panel">
          <header>
            <div>
              <h2>DigiLocker verification</h2>
              <p>{{ session.statusLabel() }}</p>
            </div>
            <button mat-button type="button" (click)="session.cancel()">Cancel</button>
          </header>

          <div class="body">
            <div class="illus" aria-hidden="true">
              <div class="window-mock">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
                <p>DigiLocker OTP</p>
              </div>
            </div>
            <ol class="steps">
              <li>A separate DigiLocker window opens (required by government policy — cannot embed here).</li>
              <li>Enter the OTP sent to the registered mobile.</li>
              <li>Return here — this screen closes automatically when verification succeeds.</li>
            </ol>
            @if (session.popupBlocked()) {
              <p class="warn">Allow pop-ups in your browser for <strong>localhost:4200</strong>.</p>
            }
            <div class="actions">
              <button mat-flat-button color="primary" type="button" (click)="session.reopenPopup()">
                {{ session.popupOpen() ? 'Bring DigiLocker to front' : 'Reopen DigiLocker' }}
              </button>
            </div>
          </div>

          <footer>
            <span class="pulse">Waiting for verification…</span>
            <span class="hint">Do not close this Payswap tab.</span>
          </footer>
        </section>
      </div>
    }
  `,
  styles: [
    `
      .backdrop {
        position: fixed;
        inset: 0;
        z-index: 10000;
        background: rgba(22, 16, 40, 0.78);
        display: grid;
        place-items: center;
        padding: 16px;
      }
      .panel {
        width: min(560px, 100%);
        background: #fff;
        border-radius: 18px;
        overflow: hidden;
        box-shadow: 0 24px 64px rgba(0, 0, 0, 0.28);
      }
      header {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: flex-start;
        padding: 16px 18px;
        border-bottom: 1px solid #ece7f5;
        background: linear-gradient(180deg, #fbf9ff, #fff);
      }
      header h2 {
        margin: 0 0 4px;
        font-size: 1.15rem;
        color: #2a2240;
      }
      header p {
        margin: 0;
        font-size: 13px;
        color: #6d6484;
        line-height: 1.45;
      }
      .body {
        padding: 18px;
        display: grid;
        gap: 14px;
      }
      .illus {
        display: grid;
        place-items: center;
        padding: 12px;
        border-radius: 14px;
        background: linear-gradient(180deg, #f3eeff, #faf8ff);
      }
      .window-mock {
        width: 220px;
        padding: 14px;
        border-radius: 12px;
        background: #fff;
        border: 1px solid #ddd4f0;
        box-shadow: 0 10px 28px rgba(42, 34, 64, 0.12);
        text-align: center;
      }
      .window-mock p {
        margin: 10px 0 0;
        font-size: 13px;
        color: #2a2240;
        font-weight: 650;
      }
      .dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #d8d0ea;
        margin-right: 4px;
      }
      .steps {
        margin: 0;
        padding-left: 18px;
        color: #3d3554;
        font-size: 13px;
        line-height: 1.55;
      }
      .warn {
        margin: 0;
        padding: 10px 12px;
        border-radius: 10px;
        background: #fff6e8;
        color: #6a3b00;
        font-size: 13px;
      }
      .actions {
        display: flex;
        justify-content: center;
      }
      footer {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 18px;
        border-top: 1px solid #ece7f5;
        font-size: 12px;
        color: #6d6484;
      }
      .pulse {
        color: #1b4dfe;
        font-weight: 650;
      }
      @media (max-width: 720px) {
        footer {
          flex-direction: column;
        }
      }
    `,
  ],
})
export class DigilockerOverlayComponent {
  readonly session = inject(DigilockerSessionService);
}
