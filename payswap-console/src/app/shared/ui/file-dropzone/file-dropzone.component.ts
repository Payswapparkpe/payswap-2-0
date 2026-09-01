import { Component, EventEmitter, Input, Output, inject, signal } from '@angular/core';
import { UploadedDoc } from '../../../core/models/onboarding.models';
import { DocumentService } from '../../../core/services/document.service';

@Component({
  selector: 'app-file-dropzone',
  standalone: true,
  template: `
    <label class="drop" [class.has-file]="value" [class.busy]="uploading()">
      <input type="file" [accept]="accept" [disabled]="uploading()" (change)="onFile($event)" />
      @if (uploading()) {
        <span class="title">Uploading…</span>
        <span class="hint">{{ pendingName() }}</span>
      } @else if (value) {
        <span class="name">{{ value.fileName }}</span>
        <span class="meta">{{ sizeLabel(value.fileSize) }} · {{ value.mimeType }}</span>
        @switch (value.reviewStatus) {
          @case ('verified') {
            <span class="badge ok">Verified</span>
          }
          @case ('rejected') {
            <span class="badge bad">Rejected — replace this file</span>
          }
          @case ('action_required') {
            <span class="badge bad">{{ value.rejectionReason || 'Replacement requested' }}</span>
          }
          @default {
            <span class="badge">Uploaded · under review</span>
          }
        }
        <button type="button" class="link" (click)="clear($event)">Replace</button>
      } @else {
        <span class="title">{{ label }}</span>
        <span class="hint">{{ hint }} · PDF, JPG or PNG up to 2 MB</span>
      }
    </label>
  `,
  styles: [
    `
      .drop {
        display: grid;
        gap: 4px;
        padding: 16px;
        border: 1.5px dashed #cfc6e4;
        border-radius: 14px;
        background: #fbfaff;
        cursor: pointer;
        position: relative;
      }
      .drop.has-file {
        border-style: solid;
        border-color: #1b4dfe55;
        background: #f3f6ff;
      }
      input {
        position: absolute;
        inset: 0;
        opacity: 0;
        cursor: pointer;
      }
      .title,
      .name {
        font-weight: 650;
        color: #13101c;
      }
      .hint,
      .meta {
        font-size: 12px;
        color: #6d6484;
      }
      .link {
        width: fit-content;
        border: 0;
        background: none;
        color: #1b4dfe;
        font-weight: 650;
        padding: 4px 0 0;
        z-index: 1;
        position: relative;
      }
      .drop.busy {
        opacity: 0.75;
        cursor: progress;
      }
      .badge {
        width: fit-content;
        font-size: 11px;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 999px;
        background: #ece7f8;
        color: #4b4266;
      }
      .badge.ok {
        background: #e3f6ea;
        color: #1c7a45;
      }
      .badge.bad {
        background: #fdeaea;
        color: #a52020;
      }
    `,
  ],
})
export class FileDropzoneComponent {
  @Input() label = 'Upload a file';
  @Input() hint = '';
  @Input() slotId = '';
  @Input() accept = '.pdf,.jpg,.jpeg,.png';
  @Input() value?: UploadedDoc;
  @Output() valueChange = new EventEmitter<UploadedDoc | undefined>();
  @Output() error = new EventEmitter<string>();

  private readonly documents = inject(DocumentService);
  readonly uploading = signal(false);
  readonly pendingName = signal('');

  onFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) {
      return;
    }
    const invalid = this.documents.validate(file);
    if (invalid) {
      this.error.emit(invalid);
      return;
    }
    this.uploading.set(true);
    this.pendingName.set(file.name);
    this.documents.upload(this.slotId, file).subscribe({
      next: (doc) => {
        this.uploading.set(false);
        this.pendingName.set('');
        this.valueChange.emit(doc);
      },
      error: (err: Error) => {
        this.uploading.set(false);
        this.pendingName.set('');
        this.error.emit(err.message || 'Upload failed. Try again.');
      },
    });
  }

  clear(event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    this.valueChange.emit(undefined);
  }

  sizeLabel(bytes: number): string {
    if (bytes < 1024) {
      return `${bytes} B`;
    }
    return `${Math.round(bytes / 1024)} KB`;
  }
}
