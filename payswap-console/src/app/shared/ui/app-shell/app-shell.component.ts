import { Component, EventEmitter, Input, Output, ViewEncapsulation, signal } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [MatIconModule],
  encapsulation: ViewEncapsulation.None,
  template: `
    <div class="shell">
      <aside class="nav" [class.open]="navOpen()">
        <ng-content select="[shell-brand]" />
        <p class="role">{{ role }}</p>
        <div class="nav-scroll">
          <ng-content select="[shell-nav]" />
        </div>
        <ng-content select="[shell-footer]" />
      </aside>

      @if (navOpen()) {
        <button
          type="button"
          class="backdrop"
          (click)="closeNav()"
          aria-label="Close navigation menu"
        ></button>
      }

      <main class="main">
        <header class="top">
          <div>
            <p class="crumb">{{ crumb }}</p>
            <h1>{{ heading }}</h1>
          </div>
          <div class="right">
            <ng-content select="[shell-header-right]" />
            <div class="identity">
              <strong>{{ userName }}</strong>
              <span>{{ userMeta }}</span>
            </div>
            <button
              type="button"
              class="menu"
              (click)="toggleNav()"
              [attr.aria-expanded]="navOpen()"
              aria-label="Toggle navigation menu"
            >
              <mat-icon>menu</mat-icon>
            </button>
          </div>
        </header>
        <section class="content">
          <ng-content />
        </section>
      </main>
    </div>
  `,
  styles: [
    `
      app-shell .shell {
        min-height: 100vh;
        display: grid;
        grid-template-columns: var(--ps-sidebar-width) minmax(0, 1fr);
        background: var(--ps-paper-strong);
      }
      app-shell .nav {
        position: sticky;
        top: 0;
        height: 100vh;
        z-index: 10;
        background: var(--ps-nav-bg);
        color: var(--ps-nav-fg);
        padding: var(--ps-space-5) var(--ps-space-3) var(--ps-space-4);
        display: flex;
        flex-direction: column;
      }
      app-shell .role {
        margin: 0 var(--ps-space-2) var(--ps-space-3);
        color: var(--ps-role-accent);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      app-shell .nav-scroll {
        min-height: 0;
        overflow: auto;
        display: grid;
        gap: 2px;
      }
      app-shell .nav :where(nav) {
        display: grid;
        gap: 4px;
      }
      app-shell .nav :where(nav a) {
        display: flex;
        gap: var(--ps-space-2);
        align-items: center;
        padding: 10px 12px;
        border-radius: var(--ps-radius-md);
        color: var(--ps-nav-link);
        font-weight: 600;
        transition: background-color 120ms ease, color 120ms ease;
      }
      app-shell .nav :where(nav a.active) {
        background: linear-gradient(100deg, var(--ps-primary), var(--ps-secondary));
        color: #fff;
      }
      app-shell .main {
        min-width: 0;
      }
      app-shell .top {
        display: flex;
        justify-content: space-between;
        gap: var(--ps-space-4);
        align-items: center;
        padding: var(--ps-space-5) var(--ps-space-7) var(--ps-space-2);
      }
      app-shell .crumb {
        margin: 0;
        font-size: 11px;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--ps-muted-strong);
        font-weight: 700;
      }
      app-shell h1 {
        margin: 4px 0 0;
        font-size: 24px;
        letter-spacing: -0.04em;
      }
      app-shell .right {
        display: flex;
        align-items: center;
        gap: var(--ps-space-3);
      }
      app-shell .identity {
        text-align: end;
        font-size: 13px;
      }
      app-shell .identity span {
        display: block;
        color: var(--ps-muted);
      }
      app-shell .menu {
        display: none;
        border: 0;
        border-radius: var(--ps-radius-pill);
        background: #fff;
        width: 38px;
        height: 38px;
        box-shadow: var(--ps-shadow-1);
      }
      app-shell .backdrop {
        position: fixed;
        inset: 0;
        border: 0;
        background: rgba(16, 16, 24, 0.5);
        z-index: 9;
      }
      app-shell .content {
        padding: var(--ps-space-2) var(--ps-space-7) var(--ps-space-8);
      }
      @media (max-width: 960px) {
        app-shell .shell {
          grid-template-columns: 1fr;
        }
        app-shell .nav {
          position: fixed;
          inset-block: 0;
          inset-inline-start: 0;
          width: min(84vw, 300px);
          transform: translateX(-102%);
          transition: transform 180ms ease;
          box-shadow: var(--ps-shadow-2);
        }
        app-shell .nav.open {
          transform: translateX(0);
        }
        app-shell .menu {
          display: inline-grid;
          place-items: center;
        }
        app-shell .top,
        app-shell .content {
          padding-inline: var(--ps-space-4);
        }
      }
    `,
  ],
})
export class AppShellComponent {
  @Input() role = '';
  @Input() crumb = '';
  @Input() heading = '';
  @Input() userName = '';
  @Input() userMeta = '';

  @Output() menuChanged = new EventEmitter<boolean>();

  readonly navOpen = signal(false);

  toggleNav(): void {
    this.navOpen.update((open) => !open);
    this.menuChanged.emit(this.navOpen());
  }

  closeNav(): void {
    this.navOpen.set(false);
    this.menuChanged.emit(false);
  }
}
