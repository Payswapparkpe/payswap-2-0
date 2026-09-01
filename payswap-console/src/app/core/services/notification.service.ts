import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';

export type NoticeTone = 'success' | 'error' | 'info';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly snack = inject(MatSnackBar);

  /** Short confirmation — e.g. OTP resent, saved. */
  success(message: string, durationMs = 2600): void {
    this.snack.open(message, 'OK', { duration: durationMs, panelClass: ['ps-snack-ok'] });
  }

  /** Use only when there is no inline alert on the page. */
  error(message: string, durationMs = 6000): void {
    this.snack.open(message, 'Dismiss', { duration: durationMs, panelClass: ['ps-snack-error'] });
  }

  /** Neutral guidance — longer read time for mismatch / policy notes. */
  info(message: string, durationMs = 7000): void {
    this.snack.open(message, 'OK', { duration: durationMs, panelClass: ['ps-snack-info'] });
  }
}
