import { Component, Input } from '@angular/core';
import { EntityType, OnboardingStep } from '../../../core/models/onboarding.models';
import { stepsForEntity } from '../../../core/config/entity-rules';

@Component({
  selector: 'app-wizard-stepper',
  standalone: true,
  template: `
    <ol class="steps" [style.gridTemplateColumns]="'repeat(' + steps.length + ', minmax(0, 1fr))'">
      @for (step of steps; track step.id; let i = $index) {
        <li [class.done]="i < activeIndex" [class.active]="i === activeIndex">
          <span class="idx">{{ i + 1 }}</span>
          <span class="lbl">{{ step.label }}</span>
        </li>
      }
    </ol>
  `,
  styles: [
    `
      .steps {
        display: grid;
        gap: 8px;
        list-style: none;
        margin: 0;
        padding: 0;
      }
      li {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
        color: #8a819d;
        font-size: 12px;
        font-weight: 650;
      }
      .idx {
        width: 22px;
        height: 22px;
        border-radius: 99px;
        display: grid;
        place-items: center;
        background: #ece8f4;
        flex: none;
      }
      .lbl {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .active {
        color: #1b4dfe;
      }
      .active .idx {
        background: #1b4dfe;
        color: #fff;
      }
      .done {
        color: #0f7a3d;
      }
      .done .idx {
        background: #d8f5e4;
        color: #0f7a3d;
      }
      @media (max-width: 800px) {
        .lbl {
          display: none;
        }
        .steps {
          justify-items: center;
        }
        li {
          justify-content: center;
        }
      }
    `,
  ],
})
export class WizardStepperComponent {
  @Input() current: OnboardingStep = 'signatory';
  @Input() entityType: EntityType | '' = '';
  @Input() signatoryIsOwner: boolean | null = null;

  get steps() {
    return stepsForEntity(this.entityType, this.signatoryIsOwner);
  }

  get activeIndex(): number {
    return this.steps.findIndex((s) => s.id === this.current);
  }
}
