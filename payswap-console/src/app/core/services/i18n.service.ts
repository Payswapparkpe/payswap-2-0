import { Injectable, computed, signal } from '@angular/core';

type LocaleKey = 'en' | 'hi';

const DICT: Record<LocaleKey, Record<string, string>> = {
  en: {
    signIn: 'Sign in',
    signOut: 'Sign out',
    orders: 'Orders',
    leads: 'Leads',
    settings: 'Settings',
  },
  hi: {
    signIn: 'साइन इन',
    signOut: 'साइन आउट',
    orders: 'ऑर्डर्स',
    leads: 'लीड्स',
    settings: 'सेटिंग्स',
  },
};

@Injectable({ providedIn: 'root' })
export class I18nService {
  readonly language = signal<LocaleKey>('en');
  readonly dictionary = computed(() => DICT[this.language()]);

  setLanguage(language: LocaleKey): void {
    this.language.set(language);
  }

  t(key: string): string {
    return this.dictionary()[key] ?? key;
  }
}
