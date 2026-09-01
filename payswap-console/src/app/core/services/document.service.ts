import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { UploadedDoc } from '../models/onboarding.models';
import { ApiService } from './api.service';

/** Max upload size accepted by the backend's document validator. */
export const MAX_DOCUMENT_BYTES = 2 * 1024 * 1024;

@Injectable({ providedIn: 'root' })
export class DocumentService {
  private readonly api = inject(ApiService);

  /**
   * Persist a wizard upload immediately. The file itself never travels inside
   * the onboarding payload — only the returned `publicId` does.
   */
  upload(slotId: string, file: File): Observable<UploadedDoc> {
    return this.api
      .upload<UploadedDoc>('/merchant/onboarding/documents/', file, { slotId })
      .pipe(
        map((doc) => ({
          ...doc,
          slotId: doc.slotId || slotId,
          fileName: doc.fileName || file.name,
          fileSize: doc.fileSize || file.size,
          mimeType: file.type || doc.mimeType || 'application/octet-stream',
          uploadStatus: 'uploaded' as const,
        })),
      );
  }

  /** Client-side guard so an oversized file never starts a doomed request. */
  validate(file: File): string {
    if (file.size > MAX_DOCUMENT_BYTES) {
      return 'Each file must be 2 MB or smaller.';
    }
    return '';
  }
}
