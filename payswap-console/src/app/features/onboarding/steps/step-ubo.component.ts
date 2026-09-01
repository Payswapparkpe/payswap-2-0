import { Component, EventEmitter, Input, Output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { KycApplication, Ubo } from '../../../core/models/onboarding.models';
import { nextOnboardingStep, prevOnboardingStep, resolvedSignatoryIsOwner, uboThreshold } from '../../../core/config/entity-rules';

@Component({
  selector: 'app-step-ubo',
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule],
  template: `
    <div>
      @if (application.profile.entityType === 'public_limited') {
        <p>Public listed companies may skip UBO identification with a declaration.</p>
        <mat-checkbox [(ngModel)]="skipListed">This entity is listed; skip UBO capture</mat-checkbox>
      } @else if (!signatoryIsOwner) {
        <p>
          Authorised-signatory KYC and business-owner KYC are already on file. List every individual
          with more than {{ threshold }}% ownership or control, including the owner already verified
          if they meet the threshold. Verify each remaining person’s KYC.
        </p>
      } @else {
        <p>
          Add every individual with more than {{ threshold }}% ownership or control
          (RBI KYC Master Direction). You can include yourself. Confirming freezes the list.
        </p>
      }

      @if (!skipListed) {
        <div class="list">
          @for (ubo of ubos; track ubo.id; let i = $index) {
            <article [class.frozen]="frozen">
              <mat-form-field appearance="outline">
                <mat-label>Name</mat-label>
                <input matInput [(ngModel)]="ubo.name" [disabled]="frozen" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>PAN</mat-label>
                <input matInput [(ngModel)]="ubo.pan" [disabled]="frozen" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Ownership %</mat-label>
                <input matInput type="number" [(ngModel)]="ubo.ownershipPercent" [disabled]="frozen" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Relationship</mat-label>
                <input matInput [(ngModel)]="ubo.relationship" [disabled]="frozen" />
              </mat-form-field>
              <button mat-stroked-button type="button" (click)="verify(ubo)" [disabled]="frozen || ubo.kycVerified">
                {{ ubo.kycVerified ? 'KYC verified' : 'Verify owner KYC (demo)' }}
              </button>
              @if (!frozen) {
                <button mat-button type="button" color="warn" (click)="remove(i)">Remove</button>
              }
            </article>
          }
        </div>
        @if (!frozen) {
          <button mat-stroked-button type="button" (click)="add()">Add owner / beneficial owner</button>
        }
        <div class="freeze">
          @if (!frozen) {
            <button mat-stroked-button type="button" (click)="frozen = true">Confirm beneficial owners</button>
          } @else {
            <p class="ok">List is frozen. Unlock only to correct errors.</p>
            <button mat-button type="button" (click)="frozen = false">Unlock for correction</button>
          }
        </div>
      }
      @if (error()) {
        <p class="error">{{ error() }}</p>
      }
      <div class="actions">
        <button mat-button type="button" (click)="back()">Back</button>
        <button mat-flat-button color="primary" type="button" (click)="next()">Save and continue</button>
      </div>
    </div>
  `,
  styles: [
    `
      .list {
        display: grid;
        gap: 12px;
        margin: 12px 0;
      }
      article {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px 12px;
        padding: 12px;
        border: 1px solid #e7e1f2;
        border-radius: 14px;
      }
      .ok {
        color: #0f7a3d;
      }
      .error {
        color: #b42318;
      }
      .actions {
        display: flex;
        justify-content: space-between;
        margin-top: 16px;
      }
      @media (max-width: 720px) {
        article {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class StepUboComponent {
  @Input({ required: true }) application!: KycApplication;
  @Output() save = new EventEmitter<KycApplication>();

  ubos: Ubo[] = [];
  frozen = false;
  skipListed = false;
  readonly error = signal('');

  get threshold(): number {
    return uboThreshold(this.application.profile.entityType);
  }

  get signatoryIsOwner(): boolean {
    return resolvedSignatoryIsOwner(this.application);
  }

  ngOnInit(): void {
    this.ubos = this.application.ubos.map((u) => ({ ...u }));
    this.frozen = this.application.ubosFrozen;
    this.skipListed = this.application.publicListedSkip;
    if (!this.ubos.length && this.signatoryIsOwner && this.application.signatory.verified) {
      this.ubos.push({
        id: crypto.randomUUID(),
        name: this.application.signatory.name,
        pan: this.application.signatory.pan,
        ownershipPercent: this.threshold + 1,
        relationship: 'Director / partner',
        kycPath: this.application.signatory.path,
        kycVerified: true,
      });
    }
  }

  add(): void {
    this.ubos.push({
      id: crypto.randomUUID(),
      name: '',
      pan: '',
      ownershipPercent: this.threshold + 1,
      relationship: 'Shareholder',
      kycVerified: false,
    });
  }

  remove(index: number): void {
    this.ubos.splice(index, 1);
  }

  verify(ubo: Ubo): void {
    ubo.kycVerified = true;
    ubo.kycPath = 'digilocker';
  }

  back(): void {
    this.save.emit({
      ...this.payload(),
      currentStep: prevOnboardingStep('ubo', this.application.profile.entityType, this.application.signatoryIsOwner),
    });
  }

  next(): void {
    this.error.set('');
    if (!this.skipListed) {
      if (!this.ubos.length) {
        this.error.set('Add at least one beneficial owner, or skip if the company is listed.');
        return;
      }
      if (this.ubos.some((u) => !u.name || !u.pan || !u.kycVerified)) {
        this.error.set('Every owner needs name, PAN, and KYC verification.');
        return;
      }
      const signatoryPan = this.application.signatory.pan.trim().toUpperCase();
      if (!this.signatoryIsOwner && this.ubos.every((u) => u.pan.trim().toUpperCase() === signatoryPan)) {
        this.error.set('Add at least one owner who is not the authorised signatory.');
        return;
      }
      if (!this.frozen) {
        this.error.set('Confirm the beneficial owner list to freeze it.');
        return;
      }
    }
    this.save.emit({
      ...this.payload(),
      currentStep: nextOnboardingStep('ubo', this.application.profile.entityType, this.application.signatoryIsOwner),
    });
  }

  private payload(): KycApplication {
    return {
      ...this.application,
      ubos: this.ubos,
      ubosFrozen: this.frozen,
      publicListedSkip: this.skipListed,
    };
  }
}
