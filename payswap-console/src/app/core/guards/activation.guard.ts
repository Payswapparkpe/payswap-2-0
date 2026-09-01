import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map, of, switchMap } from 'rxjs';
import { canAccessCommerce } from '../models/onboarding.models';
import { OnboardingService } from '../services/onboarding.service';

function withApplication(onboarding: OnboardingService) {
  if (onboarding.application()) {
    return of(onboarding.application());
  }
  return onboarding.load();
}

/** Blocks commerce routes until KYC, KYB, agreement and admin approval are complete. */
export const commerceGuard: CanActivateFn = () => {
  const onboarding = inject(OnboardingService);
  const router = inject(Router);
  return withApplication(onboarding).pipe(
    map((app) => (canAccessCommerce(app) ? true : router.createUrlTree(['/app/account']))),
  );
};

/** Profile summary pages are available only after the partner is fully activated. */
export const activatedProfileGuard: CanActivateFn = () => {
  const onboarding = inject(OnboardingService);
  const router = inject(Router);
  return withApplication(onboarding).pipe(
    map((app) => (canAccessCommerce(app) ? true : router.createUrlTree(['/app/account']))),
  );
};

/** Send dashboard home to activation hub until commerce is unlocked. */
export const appHomeGuard: CanActivateFn = () => {
  const onboarding = inject(OnboardingService);
  const router = inject(Router);
  return withApplication(onboarding).pipe(
    switchMap((app) => {
      if (canAccessCommerce(app)) {
        return of(true);
      }
      return of(router.createUrlTree(['/app/account']));
    }),
  );
};
