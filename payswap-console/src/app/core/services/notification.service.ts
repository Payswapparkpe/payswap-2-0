import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly snack = inject(MatSnackBar);

  success(message: string): void {
    this.snack.open(message, 'OK', { duration: 2200, panelClass: ['ps-snack-ok'] });
  }

  error(message: string): void {
    this.snack.open(message, 'Dismiss', { duration: 3200, panelClass: ['ps-snack-error'] });
  }
}
