import { DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { LEAD_STATUSES, LEAD_STATUS_LABELS, Lead, LeadStatus } from '../../core/models/onboarding.models';
import { OnboardingService } from '../../core/services/onboarding.service';
import { AuthService } from '../../core/services/auth.service';
import { LocaleService } from '../../core/services/locale.service';
import { NotificationService } from '../../core/services/notification.service';
import { LoadingStateComponent } from '../../shared/ui/loading-state/loading-state.component';

@Component({
  selector: 'app-lead-detail',
  standalone: true,
  imports: [
    DatePipe,
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    LoadingStateComponent,
  ],
  template: `
    <p class="back"><a [routerLink]="listLink()">← All leads</a></p>
    @if (error()) { <p class="error">{{ error() }}</p> }
    @if (lead(); as row) {
      <article class="card">
        <h2>{{ row.company }}</h2>
        <p>{{ row.contactName }} · {{ row.email }} · {{ row.mobile }}</p>
        <dl>
          <div><dt>Status</dt><dd>{{ labels[row.status] }}</dd></div>
          <div><dt>Source</dt><dd>{{ row.source }}</dd></div>
          <div><dt>Value</dt><dd>{{ locale.formatCurrency(row.valueEstimate) }}</dd></div>
          <div><dt>Notes</dt><dd>{{ row.notes || '—' }}</dd></div>
        </dl>
        <div class="row">
          <mat-form-field appearance="outline">
            <mat-label>Status</mat-label>
            <mat-select [(ngModel)]="status">
              @for (s of statuses; track s) {
                <mat-option [value]="s">{{ labels[s] }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          @if (isAdmin()) {
            <mat-form-field appearance="outline">
              <mat-label>Owner</mat-label>
              <mat-select [(ngModel)]="ownerId">
                @for (u of staff(); track u.id) {
                  <mat-option [value]="u.id">{{ u.fullName }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
          }
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Add note</mat-label>
            <input matInput [(ngModel)]="note" />
          </mat-form-field>
        </div>
        <button mat-flat-button color="primary" type="button" [disabled]="saving()" (click)="save()">
          {{ saving() ? 'Saving…' : 'Save' }}
        </button>
      </article>
      <article class="card">
        <h3>Activity</h3>
        <ul>
          @for (ev of row.activity; track ev.at + ev.text) {
            <li>
              <strong>{{ ev.status ? (labels[ev.status]) : 'Note' }}</strong>
              <span>{{ ev.at | date: 'short' }}</span>
              <p>{{ ev.text }}</p>
            </li>
          }
        </ul>
      </article>
    } @else {
      <app-loading-state label="Loading lead details..." />
    }
  `,
  styles: [
    `
      .card { background: #fff; border: 1px solid #e7e1f2; border-radius: 16px; padding: 18px; margin-bottom: 12px; }
      dl { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
      dt { font-size: 11px; text-transform: uppercase; color: #8a819d; }
      dd { margin: 0; font-weight: 650; }
      .row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
      .wide { grid-column: 1 / -1; }
      ul { list-style: none; padding: 0; display: grid; gap: 10px; }
      span { display: block; font-size: 12px; color: #8a819d; }
      .error { color: #b42318; }
    `,
  ],
})
export class LeadDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  readonly onboarding = inject(OnboardingService);
  readonly auth = inject(AuthService);
  readonly locale = inject(LocaleService);
  private readonly notify = inject(NotificationService);
  readonly statuses = LEAD_STATUSES;
  readonly labels = LEAD_STATUS_LABELS;
  readonly lead = signal<Lead | null>(null);
  readonly error = signal('');
  readonly saving = signal(false);
  readonly isAdmin = computed(() => this.auth.user()?.partnerType === 'admin');
  readonly staff = computed(() => this.onboarding.team().filter((u) => u.partnerType === 'staff'));
  status: LeadStatus = 'new';
  ownerId = '';
  note = '';

  ngOnInit(): void {
    if (this.isAdmin()) {
      this.onboarding.loadTeam().subscribe();
    }
    this.route.paramMap.subscribe((params) => {
      const id = params.get('leadId');
      if (!id) {
        return;
      }
      this.onboarding.getLead(id).subscribe({
        next: (lead) => {
          this.lead.set(lead);
          this.status = lead.status;
          this.ownerId = lead.ownerId;
        },
        error: (err: Error) => this.error.set(err.message),
      });
    });
  }

  listLink(): string {
    return this.isAdmin() ? '/admin/leads' : '/desk/leads';
  }

  save(): void {
    const row = this.lead();
    if (!row) {
      return;
    }
    this.saving.set(true);
    this.onboarding
      .updateLead(row.id, {
        status: this.status,
        ownerId: this.isAdmin() ? this.ownerId : undefined,
        activityText: this.note,
      })
      .subscribe({
        next: (lead) => {
          this.lead.set(lead);
          this.note = '';
          this.saving.set(false);
          this.notify.success('Lead updated.');
        },
        error: (err: Error) => {
          this.saving.set(false);
          this.error.set(err.message);
          this.notify.error(err.message);
        },
      });
  }
}
