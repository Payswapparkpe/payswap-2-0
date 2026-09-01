import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { DigilockerStatusResult, VerificationService } from '../../../core/services/verification.service';

@Component({
  selector: 'app-digilocker-return',
  standalone: true,
  imports: [RouterLink, MatButtonModule],
  template: `
    <main class="page">
      <section class="card">
        <h1>DigiLocker verification</h1>
        @if (busy()) {
          <p>Checking verification status…</p>
        } @else if (error()) {
          <p class="error">{{ error() }}</p>
          <a mat-flat-button color="primary" routerLink="/app/onboarding">Back to onboarding</a>
        } @else if (result()) {
          @if (result()!.status === 'AUTHENTICATED') {
            <p class="ok">Verification completed successfully.</p>
            @if (result()!.userDetails?.name) {
              <dl>
                <dt>Name</dt>
                <dd>{{ result()!.userDetails?.name }}</dd>
                @if (result()!.userDetails?.dob) {
                  <dt>Date of birth</dt>
                  <dd>{{ result()!.userDetails?.dob }}</dd>
                }
                @if (result()!.userDetails?.mobile) {
                  <dt>Mobile</dt>
                  <dd>{{ result()!.userDetails?.mobile }}</dd>
                }
              </dl>
            }
            @for (doc of result()!.documents; track doc.type) {
              <p class="doc">{{ doc.type }} · {{ doc.name }} · {{ doc.idMasked }}</p>
            }
          } @else {
            <p class="warn">Status: {{ result()!.status }}. Complete consent on DigiLocker if still pending.</p>
          }
          <a mat-flat-button color="primary" routerLink="/app/onboarding">Continue onboarding</a>
        }
      </section>
    </main>
  `,
  styles: [
    `
      .page {
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 24px;
        background: #f7f4ff;
      }
      .card {
        width: min(520px, 100%);
        padding: 24px;
        border-radius: 16px;
        background: #fff;
        box-shadow: 0 12px 32px rgba(42, 34, 64, 0.08);
      }
      dl {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 6px 16px;
        margin: 16px 0;
      }
      dt {
        font-size: 12px;
        text-transform: uppercase;
        color: #7a7190;
      }
      .ok {
        color: #0f7a3d;
        font-weight: 650;
      }
      .warn,
      .error {
        color: #b42318;
      }
      .doc {
        font-size: 13px;
        color: #3d3554;
      }
    `,
  ],
})
export class DigilockerReturnComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly verification = inject(VerificationService);

  readonly busy = signal(true);
  readonly error = signal('');
  readonly result = signal<DigilockerStatusResult | null>(null);

  ngOnInit(): void {
    const verificationId =
      this.route.snapshot.queryParamMap.get('verification_id') ||
      this.route.snapshot.queryParamMap.get('verificationId') ||
      '';
    if (!verificationId) {
      this.busy.set(false);
      this.error.set('Missing verification id in the return URL.');
      return;
    }
    this.verification.getDigilockerStatus(verificationId).subscribe({
      next: (status) => {
        this.busy.set(false);
        this.result.set(status);
      },
      error: (err: Error) => {
        this.busy.set(false);
        this.error.set(err.message || 'Could not load DigiLocker status.');
      },
    });
  }
}
