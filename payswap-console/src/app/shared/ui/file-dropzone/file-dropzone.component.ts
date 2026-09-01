import { Component, EventEmitter, Input, Output } from '@angular/core';
    import { UploadedDoc } from '../../../core/models/onboarding.models';

@Component({
  selector: 'app-file-dropzone',
  standalone: true,
  template: `
    <label class="drop" [class.has-file]="value">
      <input type="file" [accept]="accept" (change)="onFile($event)" />
      @if (value) {
        <span class="name">{{ value.fileName }}</span>
        <span class="meta">{{ sizeLabel(value.fileSize) }} · {{ value.mimeType }}</span>
        <button type="button" class="link" (click)="clear($event)">Remove</button>
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

  onFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) {
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      this.error.emit('Each file must be 2 MB or smaller.');
      return;
    }
    this.valueChange.emit({
      slotId: this.slotId,
      fileName: file.name,
      fileSize: file.size,
      mimeType: file.type || 'application/octet-stream',
    });
    const reader = new FileReader();
    reader.onload = () => {
      this.valueChange.emit({
        slotId: this.slotId,
        fileName: file.name,
        fileSize: file.size,
        mimeType: file.type || 'application/octet-stream',
        dataUrl: typeof reader.result === 'string' ? reader.result : undefined,
      });
    };
    reader.readAsDataURL(file);
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
