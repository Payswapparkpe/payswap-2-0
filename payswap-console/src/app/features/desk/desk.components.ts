import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { LogoComponent } from '../../shared/ui/logo/logo.component';
import { AuthService } from '../../core/services/auth.service';
import { AppShellComponent } from '../../shared/ui/app-shell/app-shell.component';
import { TPipe } from '../../shared/pipes/t.pipe';

@Component({
  selector: 'app-desk-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatButtonModule, MatIconModule, LogoComponent, AppShellComponent, TPipe],
  template: `
    <app-shell
      role="Lead desk"
      crumb="Staff"
      heading="Leads"
      [userName]="auth.user()?.fullName || ''"
      [userMeta]="auth.user()?.email || ''"
    >
      <div shell-brand>
        <a routerLink="/desk" class="brand"><app-logo tone="light" [compact]="true" /></a>
      </div>
      <div shell-nav>
        <nav>
          <a routerLink="/desk" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">
            <mat-icon>dashboard</mat-icon> Home
          </a>
          <a routerLink="/desk/leads" routerLinkActive="active">
            <mat-icon>handshake</mat-icon> Leads
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
      .brand { padding: 4px 10px 8px; }
      .logout { margin-top: auto; color: #b7adc9; justify-content: flex-start; }
    `,
  ],
})
export class DeskLayoutComponent {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  logout(): void {
    this.auth.logout().subscribe(() => void this.router.navigate(['/login']));
  }
}

@Component({
  selector: 'app-desk-home',
  standalone: true,
  imports: [RouterLink, MatButtonModule],
  template: `
    <p>Open assigned leads, update status, and add notes. You cannot create team users.</p>
    <a mat-flat-button color="primary" routerLink="/desk/leads">My leads</a>
  `,
})
export class DeskHomeComponent {}
