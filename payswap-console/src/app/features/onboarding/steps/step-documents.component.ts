import { Component, EventEmitter, Input, Output, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { leftoverPhysicalDocuments } from '../../../core/config/entity-documents';
import { nextOnboardingStep, prevOnboardingStep, rulesFor } from '../../../core/config/entity-rules';
import { KycApplication, UploadedDoc } from '../../../core/models/onboarding.models';
import { FileDropzoneComponent } from '../../../shared/ui/file-dropzone/file-dropzone.component';

@Component({
  selector: 'app-step-documents',
  standalone: true,
  imports: [MatButtonModule, FileDropzoneComponent],
  template: `
    <p>
      Remaining uploads for this entity (PDF, JPG, PNG, max 2 MB). Business scans (MOA, AOA, BOR) are on KYB; person KYC is DigiLocker-only.
    </p>
    <div class="slots">
      @for (slot of slots; track slot.id) {
        <app-file-dropzone
          [label]="slot.label + (slot.required ? '' : ' (optional)')"
          [hint]="slot.hint"
          [slotId]="slot.id"
          [accept]="slot.accept"
          [value]="doc(slot.id)"
          (valueChange)="setDoc(slot.id, $event)"
          (error)="error.set($event)"
        />
      }
    </div>
    @if (error()) {
      <p class="error">{{ error() }}</p>
    }
    <div class="actions">
      <button mat-button type="button" (click)="back()">Back</button>
      <button mat-flat-button color="primary" type="button" (click)="next()">Save and continue</button>
    </div>
  `,
  styles: [
    `
      .slots {
        display: grid;
        gap: 12px;
        margin: 16px 0;
      }
      .error {
        color: #b42318;
      }
      .actions {
        display: flex;
        justify-content: space-between;
      }
    `,
  ],
})
export class StepDocumentsComponent {
  @Input({ required: true }) application!: KycApplication;
  @Input() readonly = false;
  @Output() save = new EventEmitter<KycApplication>();

  docs: UploadedDoc[] = [];
  readonly error = signal('');

  get slots() {
    const gstinProvided = !!(this.application.profile.gstin && !this.application.profile.noGstin);
    return leftoverPhysicalDocuments(
      this.application.profile.entityType,
      this.application.profile.category,
      !!rulesFor(this.application.profile.entityType)?.needsKybStep,
      gstinProvided,
    );
  }

  ngOnInit(): void {
    this.docs = [...this.application.documents];
  }

  doc(slotId: string): UploadedDoc | undefined {
    return this.docs.find((d) => d.slotId === slotId);
  }

  setDoc(slotId: string, file?: UploadedDoc): void {
    this.docs = this.docs.filter((d) => d.slotId !== slotId);
    if (file) {
      this.docs.push({ ...file, slotId });
    }
  }

  back(): void {
    this.save.emit({
      ...this.payload(),
      currentStep: prevOnboardingStep('documents', this.application.profile.entityType, this.application.signatoryIsOwner),
    });
  }

  next(): void {
    const missing = this.slots.filter((s) => s.required && !this.doc(s.id));
    if (missing.length) {
      this.error.set(`Missing: ${missing.map((s) => s.label).join(', ')}`);
      return;
    }
    this.save.emit({
      ...this.payload(),
      currentStep: nextOnboardingStep('documents', this.application.profile.entityType, this.application.signatoryIsOwner),
    });
  }

  private payload(): KycApplication {
    return { ...this.application, documents: this.docs };
  }
}
