import { computed, inject, Injectable, signal } from '@angular/core';
import { isLive } from '../models/onboarding.models';
import { OnboardingService } from './onboarding.service';

export type WorkspaceMode = 'test' | 'live';

@Injectable({ providedIn: 'root' })
export class WorkspaceModeService {
  private readonly onboarding = inject(OnboardingService);
  private readonly preferred = signal<WorkspaceMode>('test');

  readonly liveUnlocked = computed(() => isLive(this.onboarding.application()));
  readonly mode = computed<WorkspaceMode>(() =>
    this.preferred() === 'live' && this.liveUnlocked() ? 'live' : 'test',
  );

  set(mode: WorkspaceMode): void {
    if (mode === 'live' && !this.liveUnlocked()) {
      return;
    }
    this.preferred.set(mode);
  }
}
