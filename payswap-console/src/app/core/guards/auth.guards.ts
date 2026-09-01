import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from '../services/auth.service';

export const verifiedGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const proceed = () => {
    const user = auth.user();
    if (!user) {
      return router.createUrlTree(['/login']);
    }
    if (!user.mobileVerified || !user.emailVerified) {
      return router.createUrlTree(['/verify']);
    }
    if (user.partnerType !== 'corporate') {
      return router.createUrlTree(['/staff-portal']);
    }
    return true;
  };
  if (auth.user()) {
    return proceed();
  }
  return auth.hydrate().pipe(map(proceed));
};

export const guestGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const proceed = () => {
    const user = auth.user();
    if (!user) {
      return true;
    }
    if (!user.mobileVerified || !user.emailVerified) {
      return router.createUrlTree(['/verify']);
    }
    return router.createUrlTree(['/app/account']);
  };
  if (auth.user()) {
    return proceed();
  }
  return auth.hydrate().pipe(map(proceed));
};
