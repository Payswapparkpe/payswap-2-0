import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { LEAD_STATUSES, LEAD_STATUS_LABELS, Lead, LeadStatus } from '../../core/models/onboarding.models';
import { OnboardingService } from '../../core/services/onboarding.service';
import { EmptyStateComponent } from '../../shared/ui/empty-state/empty-state.component';
import { LocaleService } from '../../core/services/locale.service';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-admin-leads',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    EmptyStateComponent,
  ],
  template: `
    @if (!isDesk()) {
    <article class="card">
      <h3>New lead</h3>
      <div class="grid">
        <mat-form-field appearance="outline"><mat-label>Company</mat-label><input matInput [(ngModel)]="company" /></mat-form-field>
        <mat-form-field appearance="outline"><mat-label>Contact</mat-label><input matInput [(ngModel)]="contactName" /></mat-form-field>
        <mat-form-field appearance="outline"><mat-label>Email</mat-label><input matInput [(ngModel)]="email" /></mat-form-field>
        <mat-form-field appearance="outline"><mat-label>Mobile</mat-label><input matInput [(ngModel)]="mobile" /></mat-form-field>
        <mat-form-field appearance="outline"><mat-label>Source</mat-label><input matInput [(ngModel)]="source" /></mat-form-field>
        <mat-form-field appearance="outline"><mat-label>Value (INR)</mat-label><input matInput type="number" [(ngModel)]="valueEstimate" /></mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Owner</mat-label>
          <mat-select [(ngModel)]="ownerId">
            @for (u of staff(); track u.id) {
              <mat-option [value]="u.id">{{ u.fullName }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline" class="wide"><mat-label>Notes</mat-label><input matInput [(ngModel)]="notes" /></mat-form-field>
      </div>
      @if (error()) { <p class="error">{{ error() }}</p> }
      <button mat-flat-button color="primary" type="button" (click)="create()">Create lead</button>
    </article>
    }

    <div class="board">
      @for (status of statuses; track status) {
        <section>
          <h4>{{ labels[status] }}</h4>
          @for (lead of byStatus()[status]; track lead.id) {
            <a class="tile" [routerLink]="base() + lead.id">
              <strong>{{ lead.company }}</strong>
              <span>{{ lead.contactName }}</span>
              <span>{{ locale.formatCurrency(lead.valueEstimate) }}</span>
            </a>
          } @empty {
            <app-empty-state title="No leads" message="No leads in this stage yet." />
          }
        </section>
      }
    </div>
  `,
  styles: [
    `
      .card { background: #fff; border: 1px solid #e7e1f2; border-radius: 16px; padding: 16px; margin-bottom: 14px; }
      .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
      .wide { grid-column: 1 / -1; }
      .board { display: grid; grid-template-columns: repeat(7, minmax(140px, 1fr)); gap: 8px; overflow: auto; }
      section { background: #f6f3fb; border-radius: 12px; padding: 10px; min-height: 180px; }
      h4 { margin: 0 0 8px; font-size: 12px; text-transform: uppercase; color: #8a819d; }
      .tile { display: grid; gap: 4px; background: #fff; border-radius: 10px; padding: 10px; margin-bottom: 8px; color: #13101c; }
      .tile span { font-size: 12px; color: #6d6484; }
      .error { color: #b42318; }
      @media (max-width: 900px) { .grid, .board { grid-template-columns: 1fr; } }
    `,
  ],
})
export class AdminLeadsComponent implements OnInit {
  readonly onboarding = inject(OnboardingService);
  readonly locale = inject(LocaleService);
  private readonly notify = inject(NotificationService);
  private readonly router = inject(Router);
  readonly statuses = LEAD_STATUSES;
  readonly labels = LEAD_STATUS_LABELS;
  readonly isDesk = computed(() => this.router.url.startsWith('/desk'));
  readonly base = computed(() => (this.isDesk() ? '/desk/leads/' : '/admin/leads/'));
  readonly staff = computed(() => this.onboarding.team().filter((u) => u.partnerType === 'staff'));
  readonly byStatus = computed(() => {
    const empty: Record<LeadStatus, Lead[]> = {
      new: [],
      contacted: [],
      qualified: [],
      kyc: [],
      commercial: [],
      won: [],
      lost: [],
    };
    for (const lead of this.onboarding.leads()) {
      empty[lead.status] = [...empty[lead.status], lead];
    }
    return empty;
  });
  company = '';
  contactName = '';
  email = '';
  mobile = '';
  source = 'Manual';
  valueEstimate = 0;
  ownerId = '';
  notes = '';
  readonly error = signal('');

  ngOnInit(): void {
    this.onboarding.loadLeads().subscribe();
    if (!this.isDesk()) {
      this.onboarding.loadTeam().subscribe((rows) => {
        const staff = rows.find((u) => u.partnerType === 'staff');
        if (staff && !this.ownerId) {
          this.ownerId = staff.id;
        }
      });
    }
  }

  create(): void {
    this.error.set('');
    this.onboarding
      .createLead({
        company: this.company,
        contactName: this.contactName,
        email: this.email,
        mobile: this.mobile,
        source: this.source,
        valueEstimate: this.valueEstimate,
        notes: this.notes,
        ownerId: this.ownerId,
      })
      .subscribe({
        next: () => {
          this.company = '';
          this.contactName = '';
          this.email = '';
          this.mobile = '';
          this.notes = '';
        },
        error: (err: Error) => this.error.set(err.message),
        complete: () => this.notify.success('Lead created.'),
      });
  }
}
