import { Component, computed, inject, OnInit } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { LogoComponent } from '../../../shared/ui/logo/logo.component';
import { StatusChipComponent } from '../../../shared/ui/status-chip/status-chip.component';
import { AuthService } from '../../../core/services/auth.service';
import { OnboardingService } from '../../../core/services/onboarding.service';
import { WorkspaceModeService } from '../../../core/services/workspace-mode.service';
import { isLive, PARTNER_TYPE_LABELS } from '../../../core/models/onboarding.models';
import { AppShellComponent } from '../../../shared/ui/app-shell/app-shell.component';
import { TPipe } from '../../../shared/pipes/t.pipe';

interface NavItem {
  path: string;
  label: string;
  icon: string;
  exact: boolean;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

@Component({
  selector: 'app-console-layout',
  standalone: true,
  imports: [
    RouterLink,
    RouterLinkActive,
    RouterOutlet,
    MatIconModule,
    MatButtonModule,
    LogoComponent,
    StatusChipComponent,
    AppShellComponent,
    TPipe,
  ],
  template: `
    <app-shell
      [role]="roleLabel()"
      [crumb]="title"
      [heading]="heading"
      [userName]="auth.user()?.fullName || ''"
      [userMeta]="brandName"
    >
      <div shell-brand>
        <a routerLink="/app" class="brand"><app-logo tone="light" [compact]="true" /></a>
      </div>
      <div shell-nav>
        @for (group of groups(); track group.label) {
          <p class="group-label">{{ group.label }}</p>
          <nav>
            @for (item of group.items; track item.path) {
              <a
                [routerLink]="item.path"
                routerLinkActive="active"
                [routerLinkActiveOptions]="{ exact: item.exact }"
              >
                <mat-icon>{{ item.icon }}</mat-icon>
                {{ item.label }}
              </a>
            }
          </nav>
        }
      </div>
      <div shell-footer>
        <button mat-button type="button" class="logout" (click)="logout()">
          <mat-icon>logout</mat-icon>
          {{ 'signOut' | t }}
        </button>
      </div>
      <div shell-header-right class="who">
        <div class="mode" role="group" aria-label="Workspace mode">
          <button type="button" [class.on]="mode.mode() === 'test'" (click)="mode.set('test')">Test</button>
          <button
            type="button"
            [class.on]="mode.mode() === 'live'"
            [disabled]="!mode.liveUnlocked()"
            (click)="mode.set('live')"
            title="Live ordering after KYC, KYB and dual agreement"
          >
            Live
          </button>
        </div>
        @if (onboarding.application(); as app) {
          <app-status-chip [status]="app.status" />
        }
      </div>
      <router-outlet />
    </app-shell>
  `,
  styles: [
    `
      .brand {
        padding: 2px 10px 8px;
      }
      .group-label {
        margin: 14px 10px 6px;
        font-size: 10px;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: #9a90b4;
        font-weight: 700;
      }
      nav a { font-size: 13.5px; }
      .logout {
        margin-top: auto;
        justify-content: flex-start;
        color: #b7adc9;
      }
      .who {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 13px;
      }
      .mode {
        display: flex;
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 999px;
        padding: 3px;
      }
      .mode button {
        border: 0;
        background: transparent;
        padding: 5px 12px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 12px;
        color: #6d6484;
        cursor: pointer;
      }
      .mode button.on {
        background: #13101c;
        color: #fff;
      }
      .mode button:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }
      @media (max-width: 960px) { .group-label { margin-top: 8px; } }
    `,
  ],
})
export class ConsoleLayoutComponent implements OnInit {
  readonly auth = inject(AuthService);
  readonly onboarding = inject(OnboardingService);
  readonly mode = inject(WorkspaceModeService);
  private readonly router = inject(Router);

  title = 'Orders';
  heading = 'Overview';

  readonly roleLabel = computed(() => {
    const type = this.auth.user()?.partnerType;
    if (type === 'corporate') {
      return PARTNER_TYPE_LABELS[type];
    }
    return 'Partner';
  });

  readonly groups = computed<NavGroup[]>(() => {
    return [
      {
        label: 'Commerce',
        items: [
          { path: '/app', label: 'Home', icon: 'space_dashboard', exact: true },
          { path: '/app/po', label: 'Purchase order', icon: 'description', exact: false },
          { path: '/app/orders', label: 'Orders', icon: 'shopping_bag', exact: false },
          { path: '/app/vouchers', label: 'Brand vouchers', icon: 'confirmation_number', exact: false },
          { path: '/app/cards', label: 'Prepaid cards', icon: 'credit_card', exact: false },
        ],
      },
      {
        label: 'Account',
        items: [
          { path: '/app/account', label: 'KYC · KYB · Agreement', icon: 'verified_user', exact: false },
          { path: '/app/business', label: 'Business', icon: 'apartment', exact: false },
          { path: '/app/bank', label: 'Bank accounts', icon: 'account_balance', exact: false },
          { path: '/app/documents', label: 'Documents', icon: 'folder', exact: false },
          { path: '/app/settings', label: 'Settings', icon: 'settings', exact: false },
        ],
      },
    ];
  });

  get brandName(): string {
    return this.onboarding.application()?.profile.brandName || this.auth.user()?.email || '';
  }

  ngOnInit(): void {
    this.onboarding.load().subscribe();
    this.onboarding.loadOrders().subscribe();
    this.sync(this.router.url);
    this.router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe((e) => {
      this.sync((e as NavigationEnd).urlAfterRedirects);
    });
  }

  logout(): void {
    this.auth.logout().subscribe(() => void this.router.navigate(['/login']));
  }

  private sync(url: string): void {
    const map: [string, string, string][] = [
      ['/app/orders/', 'Commerce', 'Order details'],
      ['/app/orders', 'Commerce', 'Orders'],
      ['/app/po', 'Commerce', 'Purchase order'],
      ['/app/vouchers', 'Commerce', 'Brand vouchers'],
      ['/app/cards', 'Commerce', 'Prepaid cards'],
      ['/app/account', 'Account', 'Activation'],
      ['/app/onboarding', 'Account', 'KYC & KYB'],
      ['/app/agreement', 'Account', 'Partner agreement'],
      ['/app/business', 'Account', 'Business profile'],
      ['/app/bank', 'Account', 'Bank accounts'],
      ['/app/documents', 'Account', 'Documents'],
      ['/app/settings', 'Account', 'Settings'],
    ];
    const hit = map.find(([path]) => url.includes(path));
    if (hit) {
      this.title = hit[1];
      this.heading = hit[2];
      return;
    }
    this.title = 'Commerce';
    this.heading = isLive(this.onboarding.application()) ? 'Overview' : 'Overview · test catalog';
  }
}
