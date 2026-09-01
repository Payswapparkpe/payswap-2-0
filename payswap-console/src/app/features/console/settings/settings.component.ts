import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { AuthService } from '../../../core/services/auth.service';
import { StorageService } from '../../../core/services/storage.service';
import { Router } from '@angular/router';
import { LocaleService } from '../../../core/services/locale.service';
import { SUPPORTED_MARKETS } from '../../../core/config/market.config';
import { I18nService } from '../../../core/services/i18n.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [MatButtonModule, MatFormFieldModule, MatSelectModule, FormsModule],
  template: `
    <article class="card">
      <h3>Session</h3>
      <p>Signed in as <strong>{{ auth.user()?.email }}</strong> · {{ locale.market().dialingCode }} {{ auth.user()?.mobile }}</p>
      <button mat-stroked-button type="button" (click)="logout()">Sign out</button>
    </article>
    <article class="card">
      <h3>Regional preferences</h3>
      <p>Set locale, currency, and timezone presets for a global-ready experience.</p>
      <mat-form-field appearance="outline">
        <mat-label>Language</mat-label>
        <mat-select [ngModel]="lang" (ngModelChange)="setLang($event)">
          <mat-option value="en">English</mat-option>
          <mat-option value="hi">Hindi</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Market preset</mat-label>
        <mat-select [ngModel]="marketCode" (ngModelChange)="setMarket($event)">
          @for (opt of marketOptions; track opt.code) {
            <mat-option [value]="opt.code">{{ opt.label }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <p class="meta">
        Locale: <code>{{ locale.locale() }}</code> · Currency: <code>{{ locale.market().currency }}</code> · Timezone:
        <code>{{ locale.market().timezone }}</code>
      </p>
    </article>
    <article class="card">
      <h3>Demo data</h3>
      <p>Reset restores the seeded Acme Pvt Ltd draft and clears other accounts on this browser.</p>
      <button mat-stroked-button color="warn" type="button" (click)="reset()">Reset local demo data</button>
    </article>
  `,
  styles: [
    `
      .card {
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 18px;
        padding: 22px;
        margin-bottom: 16px;
        max-width: 640px;
      }
      p {
        color: #6d6484;
      }
      .meta {
        margin-top: 6px;
        font-size: 13px;
      }
      code {
        background: #ece8f6;
        border-radius: 6px;
        padding: 1px 6px;
      }
    `,
  ],
})
export class SettingsComponent {
  readonly auth = inject(AuthService);
  readonly locale = inject(LocaleService);
  readonly i18n = inject(I18nService);
  private readonly storage = inject(StorageService);
  private readonly router = inject(Router);
  readonly marketOptions = [
    { code: 'in', label: 'India (INR, Asia/Kolkata)' },
    { code: 'us', label: 'United States (USD, America/New_York)' },
  ];
  lang: 'en' | 'hi' = this.i18n.language();
  marketCode: 'in' | 'us' = this.locale.market().currency === SUPPORTED_MARKETS['us'].currency ? 'us' : 'in';

  logout(): void {
    this.auth.logout().subscribe(() => void this.router.navigate(['/login']));
  }

  reset(): void {
    this.storage.reset();
    this.auth.logout().subscribe(() => void this.router.navigate(['/login']));
  }

  setMarket(code: 'in' | 'us'): void {
    this.marketCode = code;
    this.locale.setMarket(code);
  }

  setLang(value: 'en' | 'hi'): void {
    this.lang = value;
    this.i18n.setLanguage(value);
  }
}
