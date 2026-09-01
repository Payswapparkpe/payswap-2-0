import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { LogoComponent } from '../../shared/ui/logo/logo.component';
import { AuthService } from '../../core/services/auth.service';
import { AppShellComponent } from '../../shared/ui/app-shell/app-shell.component';
import { TPipe } from '../../shared/pipes/t.pipe';

@Component({
  selector: 'app-admin-shell-layout',
  standalone: true,
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatButtonModule,
    MatIconModule,
    LogoComponent,
    AppShellComponent,
    TPipe,
  ],
  template: `
    <app-shell
      role="Payswap admin"
      crumb="Admin"
      [heading]="heading"
      [userName]="auth.user()?.fullName || ''"
      [userMeta]="auth.user()?.email || ''"
    >
      <div shell-brand>
        <a routerLink="/admin" class="brand"><app-logo tone="light" [compact]="true" /></a>
      </div>
      <div shell-nav>
        <nav>
          <a routerLink="/admin" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">
            <mat-icon>dashboard</mat-icon> Overview
          </a>
          <a routerLink="/admin/partners" routerLinkActive="active">
            <mat-icon>groups</mat-icon> Partners
          </a>
          <a routerLink="/admin/orders" routerLinkActive="active">
            <mat-icon>shopping_bag</mat-icon> Orders
          </a>
          <a routerLink="/admin/leads" routerLinkActive="active">
            <mat-icon>handshake</mat-icon> Leads
          </a>
          <a routerLink="/admin/team" routerLinkActive="active">
            <mat-icon>badge</mat-icon> Team
          </a>
          <a routerLink="/admin/mail" routerLinkActive="active">
            <mat-icon>mail</mat-icon> Mail log
          </a>
        </nav>
      </div>
      <div shell-footer>
        <button mat-button type="button" class="logout" (click)="logout()">
          <mat-icon>logout</mat-icon> {{ 'signOut' | t }}
        </button>
      </div>
      <router-outlet />
    </app-shell>
  `,
  styles: [
    `
      .brand {
        padding: 4px 10px 8px;
      }
      .logout {
        margin-top: auto;
        color: #b7adc9;
        justify-content: flex-start;
      }
    `,
  ],
})
export class AdminLayoutShellComponent {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  heading = 'Overview';

  constructor() {
    this.router.events.subscribe(() => {
      const url = this.router.url;
      if (url.includes('/partners/')) this.heading = 'Partner file';
      else if (url.includes('/partners')) this.heading = 'Partners';
      else if (url.includes('/orders/')) this.heading = 'Order details';
      else if (url.includes('/orders')) this.heading = 'Orders';
      else if (url.includes('/leads/')) this.heading = 'Lead';
      else if (url.includes('/leads')) this.heading = 'Leads';
      else if (url.includes('/team')) this.heading = 'Team';
      else if (url.includes('/mail')) this.heading = 'Mail log';
      else this.heading = 'Overview';
    });
  }

  logout(): void {
    this.auth.logout().subscribe(() => void this.router.navigate(['/login']));
  }
}
