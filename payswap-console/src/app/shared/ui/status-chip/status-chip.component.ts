import { Component, Input } from '@angular/core';
import { AccountStatus } from '../../../core/models/onboarding.models';

@Component({
  selector: 'app-status-chip',
  standalone: true,
  template: `<span class="chip" [attr.data-status]="status">{{ label }}</span>`,
  styles: [
    `
      .chip {
        display: inline-flex;
        align-items: center;
        height: 26px;
        padding: 0 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.02em;
        background: #ece8f6;
        color: #4a3f66;
      }
      .chip[data-status='draft'],
      .chip[data-status='registered'] {
        background: #efe8ff;
        color: #6b21a8;
      }
      .chip[data-status='under_review'] {
        background: #fff4e5;
        color: #9a4b00;
      }
      .chip[data-status='pending_agreement'] {
        background: #e7eeff;
        color: #1b4dfe;
      }
      .chip[data-status='pending_admin_sign'] {
        background: #fff4e5;
        color: #9a4b00;
      }
      .chip[data-status='activated'] {
        background: #e6f8ee;
        color: #0f7a3d;
      }
      .chip[data-status='pending_mobile_otp'],
      .chip[data-status='pending_email_otp'] {
        background: #e7eeff;
        color: #1b4dfe;
      }
    `,
  ],
})
export class StatusChipComponent {
  @Input({ required: true }) status!: AccountStatus;

  get label(): string {
    const map: Record<AccountStatus, string> = {
      pending_mobile_otp: 'Verify mobile',
      pending_email_otp: 'Verify email',
      registered: 'Registered',
      draft: 'KYC / KYB in progress',
      under_review: 'Awaiting admin verify',
      pending_agreement: 'Sign agreement',
      pending_admin_sign: 'Awaiting admin sign',
      activated: 'Live partner',
    };
    return map[this.status] ?? this.status;
  }
}
