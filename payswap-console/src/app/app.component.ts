import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { DigilockerOverlayComponent } from './shared/ui/digilocker-overlay/digilocker-overlay.component';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, DigilockerOverlayComponent],
  template: `
    <router-outlet />
    <app-digilocker-overlay />
  `,
})
export class AppComponent {}
