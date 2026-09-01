import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { OnboardingService } from '../../core/services/onboarding.service';

@Component({
  selector: 'app-admin-team',
  standalone: true,
  imports: [DatePipe, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule],
  template: `
    <article class="card">
      <h3>Add staff user</h3>
      <p class="hint">They sign in at the lead desk. Default password is Payswap&#64;123.</p>
      <div class="row">
        <mat-form-field appearance="outline"><mat-label>Name</mat-label><input matInput [(ngModel)]="fullName" /></mat-form-field>
        <mat-form-field appearance="outline"><mat-label>Email</mat-label><input matInput [(ngModel)]="email" /></mat-form-field>
        <mat-form-field appearance="outline"><mat-label>Mobile</mat-label><input matInput [(ngModel)]="mobile" /></mat-form-field>
      </div>
      @if (error()) { <p class="error">{{ error() }}</p> }
      @if (ok()) { <p class="ok">{{ ok() }}</p> }
      <button mat-flat-button color="primary" type="button" (click)="create()">Create staff user</button>
    </article>
    <article class="card">
      <h3>Team</h3>
      <table>
        <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Created</th></tr></thead>
        <tbody>
          @for (row of onboarding.team(); track row.id) {
            <tr>
              <td>{{ row.fullName }}</td>
              <td>{{ row.email }}</td>
              <td>{{ row.partnerType }}</td>
              <td>{{ row.createdAt | date: 'short' }}</td>
            </tr>
          }
        </tbody>
      </table>
    </article>
  `,
  styles: [
    `
      .card { background: #fff; border: 1px solid #e7e1f2; border-radius: 16px; padding: 18px; margin-bottom: 12px; }
      .row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
      .hint, td { color: #6d6484; }
      table { width: 100%; border-collapse: collapse; font-size: 13px; }
      th { text-align: left; font-size: 11px; text-transform: uppercase; color: #8a819d; padding: 8px; }
      td { padding: 10px 8px; border-top: 1px solid #f0ebf7; }
      .error { color: #b42318; }
      .ok { color: #0f7a3d; }
      @media (max-width: 800px) { .row { grid-template-columns: 1fr; } }
    `,
  ],
})
export class AdminTeamComponent implements OnInit {
  readonly onboarding = inject(OnboardingService);
  fullName = '';
  email = '';
  mobile = '';
  readonly error = signal('');
  readonly ok = signal('');

  ngOnInit(): void {
    this.onboarding.loadTeam().subscribe();
  }

  create(): void {
    this.error.set('');
    this.ok.set('');
    this.onboarding.createStaff({ fullName: this.fullName, email: this.email, mobile: this.mobile }).subscribe({
      next: (user) => {
        this.ok.set(`${user.fullName} can sign in as staff.`);
        this.fullName = '';
        this.email = '';
        this.mobile = '';
      },
      error: (err: Error) => this.error.set(err.message),
    });
  }
}
