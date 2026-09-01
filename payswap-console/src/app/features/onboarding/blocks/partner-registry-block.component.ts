import { Component, EventEmitter, Input, OnChanges, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { EntityType, RegistryDirector, UploadedDoc } from '../../../core/models/onboarding.models';
import { registryDeedSlotId } from '../../../core/config/entity-documents';
import { FileDropzoneComponent } from '../../../shared/ui/file-dropzone/file-dropzone.component';

@Component({
  selector: 'app-partner-registry-block',
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, FileDropzoneComponent],
  template: `
    <section class="registry">
      <header>
        <h4>{{ entityType === 'partnership' ? 'Partners' : 'Trustees / office bearers' }}</h4>
        <p>
          Add every {{ entityType === 'partnership' ? 'partner' : 'trustee' }} who must complete KYC. Optionally
          upload the deed — OCR will suggest names you can edit before saving.
        </p>
      </header>

      @if (deedSlotId) {
        <app-file-dropzone
          [label]="entityType === 'partnership' ? 'Partnership deed (optional)' : 'Trust deed (optional)'"
          hint="Upload PDF or image. Partner/trustee names will be extracted when OCR is enabled."
          [slotId]="deedSlotId"
          [value]="deedDoc"
          (valueChange)="onDeedChange($event)"
        />
      }

      @for (member of members; track memberKey(member); let i = $index) {
        <article class="member-card">
          <mat-form-field appearance="outline">
            <mat-label>Full name</mat-label>
            <input matInput [(ngModel)]="member.name" [disabled]="readonly" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>PAN</mat-label>
            <input matInput [(ngModel)]="member.pan" class="mono" [disabled]="readonly" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Designation</mat-label>
            <input
              matInput
              [(ngModel)]="member.designation"
              [placeholder]="entityType === 'partnership' ? 'Partner' : 'Trustee'"
              [disabled]="readonly"
            />
          </mat-form-field>
          @if (!readonly) {
            <button mat-button type="button" color="warn" (click)="remove(i)">Remove</button>
          }
        </article>
      }

      @if (!readonly) {
        <button mat-stroked-button type="button" (click)="add()">
          Add {{ entityType === 'partnership' ? 'partner' : 'trustee' }}
        </button>
      }

      <p class="count">{{ members.length }} listed · KYC collected on UBO step</p>
    </section>
  `,
  styles: [
    `
      .registry {
        display: grid;
        gap: 12px;
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px dashed #ddd5ee;
      }
      header h4 {
        margin: 0 0 4px;
      }
      header p,
      .count {
        margin: 0;
        font-size: 13px;
        color: #6d6484;
        line-height: 1.45;
      }
      .member-card {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr auto;
        gap: 8px;
        align-items: start;
        padding: 12px;
        border: 1px solid #e7e1f2;
        border-radius: 12px;
        background: #fff;
      }
      .mono {
        font-family: ui-monospace, monospace;
      }
      @media (max-width: 720px) {
        .member-card {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class PartnerRegistryBlockComponent implements OnChanges {
  @Input({ required: true }) entityType!: EntityType;
  @Input({ required: true }) members: RegistryDirector[] = [];
  @Input() deedDoc?: UploadedDoc;
  @Input() readonly = false;
  @Output() membersChange = new EventEmitter<RegistryDirector[]>();
  @Output() deedChange = new EventEmitter<UploadedDoc | undefined>();

  deedSlotId: string | null = null;

  ngOnChanges(): void {
    this.deedSlotId = registryDeedSlotId(this.entityType);
  }

  memberKey(member: RegistryDirector): string {
    return member.din || member.pan || member.name;
  }

  add(): void {
    this.membersChange.emit([
      ...this.members,
      {
        name: '',
        din: '',
        designation: this.entityType === 'partnership' ? 'Partner' : 'Trustee',
        dob: '',
        address: '',
        pan: '',
        kycVerified: false,
      },
    ]);
  }

  remove(index: number): void {
    this.membersChange.emit(this.members.filter((_, i) => i !== index));
  }

  onDeedChange(file?: UploadedDoc): void {
    if (!file) {
      this.deedChange.emit(undefined);
      return;
    }
    this.deedChange.emit({
      ...file,
      ocrPayload: { status: 'pending', message: 'OCR processing queued' },
    });
  }
}
