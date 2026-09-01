import { registerLocaleData } from '@angular/common';
import localeEnIn from '@angular/common/locales/en-IN';
import localeEnUs from '@angular/common/locales/en';
import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';

registerLocaleData(localeEnIn);
registerLocaleData(localeEnUs);

bootstrapApplication(AppComponent, appConfig)
  .catch((err) => console.error(err));
