import { Injectable, inject, signal } from '@angular/core';
import { Observable, Subject, finalize, switchMap, takeUntil, throwError } from 'rxjs';
import { DigilockerStatusResult, VerificationService } from './verification.service';

export interface DigilockerSessionOptions {
  mobile: string;
  pan: string;
  name: string;
}

@Injectable({ providedIn: 'root' })
export class DigilockerSessionService {
  private readonly verification = inject(VerificationService);

  readonly active = signal(false);
  readonly url = signal('');
  readonly statusLabel = signal('Starting DigiLocker…');
  readonly popupOpen = signal(false);
  readonly popupBlocked = signal(false);

  private popup: Window | null = null;
  private popupWatchId: number | null = null;
  private readonly cancel$ = new Subject<void>();

  /**
   * DigiLocker blocks iframe embedding (X-Frame-Options). The supported UX is a
   * centered popup while this Payswap overlay stays open and polls for success.
   */
  run(options: DigilockerSessionOptions): Observable<DigilockerStatusResult> {
    const pan = options.pan.trim().toUpperCase();
    const mobile = options.mobile.trim();
    const name = options.name.trim();
    this.cancel$.next();
    this.statusLabel.set('Checking DigiLocker account…');
    return this.verification.verifyDigilockerAccount(mobile, pan).pipe(
      switchMap((account) => {
        if (account.status === 'ACCOUNT_NOT_FOUND') {
          return throwError(() => new Error('No DigiLocker account linked to this mobile number.'));
        }
        this.statusLabel.set('Opening DigiLocker…');
        return this.verification.createDigilockerUrl();
      }),
      switchMap((session) => {
        this.begin(session.url);
        return this.verification.pollDigilockerStatus(session.verificationId, pan, name).pipe(
          takeUntil(this.cancel$),
          finalize(() => this.close()),
        );
      }),
    );
  }

  sync(verificationId: string, pan = '', name = ''): Observable<DigilockerStatusResult> {
    this.cancel$.next();
    this.statusLabel.set('Checking DigiLocker status…');
    this.active.set(true);
    this.popupOpen.set(false);
    this.popupBlocked.set(false);
    return this.verification.getDigilockerStatus(verificationId, pan, name).pipe(
      takeUntil(this.cancel$),
      finalize(() => this.close()),
    );
  }

  cancel(): void {
    this.cancel$.next();
    this.close();
  }

  reopenPopup(): void {
    if (this.popup && !this.popup.closed) {
      this.popup.focus();
      this.popupOpen.set(true);
      this.popupBlocked.set(false);
      this.statusLabel.set('Complete OTP in the DigiLocker window. Keep this Payswap screen open.');
      return;
    }
    this.launchPopup();
  }

  private begin(url: string): void {
    this.active.set(true);
    this.url.set(url);
    this.launchPopup();
  }

  private launchPopup(): void {
    const url = this.url();
    if (!url) {
      return;
    }
    const width = 520;
    const height = 780;
    const left = Math.round(window.screenX + Math.max(0, (window.outerWidth - width) / 2));
    const top = Math.round(window.screenY + Math.max(0, (window.outerHeight - height) / 2));
    const features = [
      'popup=yes',
      `width=${width}`,
      `height=${height}`,
      `left=${left}`,
      `top=${top}`,
      'resizable=yes',
      'scrollbars=yes',
      'noopener=no',
    ].join(',');
    this.popup = window.open(url, 'payswap_digilocker', features);
    if (!this.popup) {
      this.popupBlocked.set(true);
      this.popupOpen.set(false);
      this.statusLabel.set('Pop-ups are blocked. Allow pop-ups for this site, then click Reopen DigiLocker.');
      return;
    }
    this.popupBlocked.set(false);
    this.popupOpen.set(true);
    this.statusLabel.set('Complete OTP in the DigiLocker window. This overlay closes automatically on success.');
    this.watchPopup();
  }

  private watchPopup(): void {
    this.stopPopupWatch();
    this.popupWatchId = window.setInterval(() => {
      if (!this.popup || this.popup.closed) {
        this.popupOpen.set(false);
        if (this.active()) {
          this.statusLabel.set('DigiLocker window closed. Click Reopen if verification is not finished yet.');
        }
        this.stopPopupWatch();
      }
    }, 800);
  }

  private stopPopupWatch(): void {
    if (this.popupWatchId !== null) {
      window.clearInterval(this.popupWatchId);
      this.popupWatchId = null;
    }
  }

  private close(): void {
    this.active.set(false);
    this.url.set('');
    this.popupOpen.set(false);
    this.popupBlocked.set(false);
    this.stopPopupWatch();
    if (this.popup && !this.popup.closed) {
      this.popup.close();
    }
    this.popup = null;
  }
}
