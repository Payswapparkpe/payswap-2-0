import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { WizardStepperComponent } from '../../../shared/ui/wizard-stepper/wizard-stepper.component';
import { OnboardingService } from '../../../core/services/onboarding.service';
import {
  isApplicationEditable,
  isOnboardingReadOnly,
  isOnboardingScreenLocked,
  KycApplication,
  OnboardingStep,
} from '../../../core/models/onboarding.models';
import { StepProfileComponent } from '../steps/step-profile.component';
import { StepIdentityComponent } from '../steps/step-identity.component';
import { StepSignatoryComponent } from '../steps/step-signatory.component';
import { StepOwnerComponent } from '../steps/step-owner.component';
import { StepAuthSignatoryComponent } from '../steps/step-auth-signatory.component';
import { StepUboComponent } from '../steps/step-ubo.component';
import { StepBankComponent } from '../steps/step-bank.component';
import { StepDocumentsComponent } from '../steps/step-documents.component';
import { StepReviewComponent } from '../steps/step-review.component';
import { LoadingStateComponent } from '../../../shared/ui/loading-state/loading-state.component';

@Component({
  selector: 'app-onboarding-wizard',
  standalone: true,
  imports: [
    RouterLink,
    WizardStepperComponent,
    StepProfileComponent,
    StepIdentityComponent,
    StepSignatoryComponent,
    StepOwnerComponent,
    StepAuthSignatoryComponent,
    StepUboComponent,
    StepBankComponent,
    StepDocumentsComponent,
    StepReviewComponent,
    LoadingStateComponent,
  ],
  template: `
    @if (onboarding.application(); as app) {
      <div class="wizard">
        @if (screenLocked(app)) {
          <div class="locked">
            <h2>Application locked</h2>
            <p>Your account is active. View submitted details from the profile pages.</p>
            @if (app.returnReason) {
              <p class="warn">Admin note: {{ app.returnReason }}</p>
            }
            <a routerLink="/app/account">Back to activation</a>
          </div>
        } @else {
          <app-wizard-stepper
            [current]="app.currentStep"
            [entityType]="app.profile.entityType"
            [signatoryIsOwner]="app.signatoryIsOwner"
            [kycPersonIsAuthorisedSignatory]="app.kycPersonIsAuthorisedSignatory"
          />
          @if (readOnly(app)) {
            <p class="readonly-banner">Submitted for review — you can browse each step but cannot change values.</p>
          }
          @if (app.returnReason) {
            <p class="warn">Admin returned this file for correction: {{ app.returnReason }}</p>
          }
          @if (editable(app)) {
            <p class="save">{{ onboarding.saving() ? 'Saving draft…' : 'Draft saves as you continue.' }}</p>
          }
          @switch (app.currentStep) {
            @case ('signatory') {
              <app-step-signatory [application]="app" [readonly]="readOnly(app)" (save)="persist($event)" />
            }
            @case ('profile') {
              <app-step-profile [application]="app" [readonly]="readOnly(app)" (save)="persist($event)" />
            }
            @case ('auth_signatory') {
              <app-step-auth-signatory [application]="app" [readonly]="readOnly(app)" (save)="persist($event)" />
            }
            @case ('owner') {
              <app-step-owner [application]="app" [readonly]="readOnly(app)" (save)="persist($event)" />
            }
            @case ('identity') {
              <app-step-identity [application]="app" [readonly]="readOnly(app)" (save)="persist($event)" />
            }
            @case ('ubo') {
              <app-step-ubo [application]="app" [readonly]="readOnly(app)" (save)="persist($event)" />
            }
            @case ('bank') {
              <app-step-bank [application]="app" [readonly]="readOnly(app)" (save)="persist($event)" />
            }
            @case ('documents') {
              <app-step-documents [application]="app" [readonly]="readOnly(app)" (save)="persist($event)" />
            }
            @case ('review') {
              <app-step-review [application]="app" [readonly]="readOnly(app)" (save)="persist($event)" />
            }
          }
        }
      </div>
    } @else {
      <app-loading-state label="Loading onboarding profile..." />
    }
  `,
  styles: [
    `
      .wizard {
        background: #fff;
        border: 1px solid #e7e1f2;
        border-radius: 18px;
        padding: 22px;
      }
      .locked {
        max-width: 560px;
      }
      .locked h2 {
        margin: 0 0 10px;
      }
      .locked p {
        color: #6d6484;
        line-height: 1.5;
      }
      .locked a {
        display: inline-block;
        margin-top: 14px;
        font-weight: 700;
      }
      .warn {
        margin: 12px 0;
        padding: 12px 14px;
        border-radius: 12px;
        background: #fff4e8;
        color: #9a4b00;
        font-size: 13px;
      }
      .save {
        color: #8a819d;
        font-size: 12px;
        margin: 14px 0 8px;
      }
      .readonly-banner {
        margin: 12px 0 0;
        padding: 10px 12px;
        border-radius: 12px;
        background: #eef3ff;
        color: #1b4dfe;
        font-size: 13px;
        font-weight: 650;
      }
    `,
  ],
})
export class OnboardingWizardComponent implements OnInit {
  readonly onboarding = inject(OnboardingService);
  readonly editable = isApplicationEditable;
  readonly readOnly = isOnboardingReadOnly;
  readonly screenLocked = isOnboardingScreenLocked;

  ngOnInit(): void {
    if (!this.onboarding.application()) {
      this.onboarding.load().subscribe();
    }
  }

  persist(application: KycApplication): void {
    const current = this.onboarding.application();
    if (current && isOnboardingReadOnly(current)) {
      if (application.currentStep !== current.currentStep) {
        this.onboarding.navigateStep(application.currentStep);
      }
      return;
    }
    if (!isApplicationEditable(application)) {
      return;
    }
    this.onboarding.save(application).subscribe();
  }
}
