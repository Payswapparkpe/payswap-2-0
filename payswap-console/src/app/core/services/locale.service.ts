import { Injectable, signal } from '@angular/core';
import { DEFAULT_MARKET, SUPPORTED_MARKETS } from '../config/market.config';

const LOCALE_KEY = 'payswap-locale';
const MARKET_KEY = 'payswap-market';

@Injectable({ providedIn: 'root' })
export class LocaleService {
  readonly locale = signal(this.readLocale());
  readonly market = signal(this.readMarket());

  setLocale(next: string): void {
    this.locale.set(next);
    localStorage.setItem(LOCALE_KEY, next);
  }

  setMarket(code: string): void {
    const selected = SUPPORTED_MARKETS[code] || DEFAULT_MARKET;
    this.market.set(selected);
    this.setLocale(selected.locale);
    localStorage.setItem(MARKET_KEY, code);
  }

  formatCurrency(amount: number): string {
    return new Intl.NumberFormat(this.locale(), {
      style: 'currency',
      currency: this.market().currency,
      maximumFractionDigits: 0,
    }).format(amount);
  }

  formatDate(iso: string, options?: Intl.DateTimeFormatOptions): string {
    return new Intl.DateTimeFormat(this.locale(), {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: this.market().timezone,
      ...options,
    }).format(new Date(iso));
  }

  private readLocale(): string {
    return localStorage.getItem(LOCALE_KEY) || DEFAULT_MARKET.locale;
  }

  private readMarket() {
    const code = localStorage.getItem(MARKET_KEY) || 'in';
    return SUPPORTED_MARKETS[code] || DEFAULT_MARKET;
  }
}
