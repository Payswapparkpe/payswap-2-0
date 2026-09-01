import { Component, inject, OnInit } from '@angular/core';
import { WizardStepperComponent } from '../../../shared/ui/wizard-stepper/wizard-stepper.component';
import { OnboardingService } from '../../../core/services/onboarding.service';
import { KycApplication } from '../../../core/models/onboarding.models';
import { StepProfileComponent } from '../steps/step-profile.component';
import { StepIdentityComponent } from '../steps/step-identity.component';
import { StepSignatoryComponent } from '../steps/step-signatory.component';
import { StepOwnerComponent } from '../steps/step-owner.component';
import { StepUboComponent } from '../steps/step-ubo.component';
import { StepBankComponent } from '../steps/step-bank.component';
import { StepDocumentsComponent } from '../steps/step-documents.component';
import { StepReviewComponent } from '../steps/step-review.component';
import { LoadingStateComponent } from '../../../shared/ui/loading-state/loading-state.component';

@Component({
  selector: 'app-onboarding-wizard',
  standalone: true,
  imports: [
    WizardStepperComponent,
    StepProfileComponent,
    StepIdentityComponent,
    StepSignatoryComponent,
    StepOwnerComponent,
    StepUboComponent,
    StepBankComponent,
    StepDocumentsComponent,
    StepReviewComponent,
    LoadingStateComponent,
  ],
  template: `
    @if (onboarding.application(); as app) {
      <div class="wizard">
        <app-wizard-stepper
          [current]="app.currentStep"
          [entityType]="app.profile.entityType"
          [signatoryIsOwner]="app.signatoryIsOwner"
        />
        <p class="save">{{ onboarding.saving() ? 'Saving draft…' : 'Draft saves as you continue.' }}</p>
        @switch (app.currentStep) {
          @case ('signatory') {
            <app-step-signatory [application]="app" (save)="persist($event)" />
          }
          @case ('profile') {
            <app-step-profile [application]="app" (save)="persist($event)" />
          }
          @case ('owner') {
            <app-step-owner [application]="app" (save)="persist($event)" />
          }
          @case ('identity') {
            <app-step-identity [application]="app" (save)="persist($event)" />
          }
          @case ('ubo') {
            <app-step-ubo [application]="app" (save)="persist($event)" />
          }
          @case ('bank') {
            <app-step-bank [application]="app" (save)="persist($event)" />
          }
          @case ('documents') {
            <app-step-documents [application]="app" (save)="persist($event)" />
          }
          @case ('review') {
            <app-step-review [application]="app" (save)="persist($event)" />
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
      .save {
        color: #8a819d;
        font-size: 12px;
        margin: 14px 0 8px;
      }
    `,
  ],
})
export class OnboardingWizardComponent implements OnInit {
  readonly onboarding = inject(OnboardingService);

  ngOnInit(): void {
    if (!this.onboarding.application()) {
      this.onboarding.load().subscribe();
    }
  }

  persist(application: KycApplication): void {
    this.onboarding.save(application).subscribe();
  }
}
