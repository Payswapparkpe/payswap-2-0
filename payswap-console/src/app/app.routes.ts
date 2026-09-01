import { Routes } from '@angular/router';
import { activatedProfileGuard, appHomeGuard, commerceGuard } from './core/guards/activation.guard';
import { guestGuard, verifiedGuard } from './core/guards/auth.guards';

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'register',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/register/register.component').then((m) => m.RegisterComponent),
  },
  {
    path: 'verify',
    loadComponent: () => import('./features/auth/verify/verify.component').then((m) => m.VerifyComponent),
  },
  {
    path: 'digilocker-return',
    loadComponent: () =>
      import('./features/auth/digilocker-return/digilocker-return.component').then((m) => m.DigilockerReturnComponent),
  },
  {
    path: 'forgot-password',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/forgot-password/forgot-password.component').then((m) => m.ForgotPasswordComponent),
  },
  {
    path: 'reset-password/:uid/:token',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/reset-password/reset-password.component').then((m) => m.ResetPasswordComponent),
  },
  {
    path: 'staff-portal',
    loadComponent: () =>
      import('./features/auth/staff-portal/staff-portal.component').then((m) => m.StaffPortalComponent),
  },
  {
    path: 'app',
    canActivate: [verifiedGuard],
    loadComponent: () =>
      import('./features/console/layout/console-layout.component').then((m) => m.ConsoleLayoutComponent),
    children: [
      {
        path: '',
        canActivate: [appHomeGuard],
        loadComponent: () => import('./features/console/home/home.component').then((m) => m.HomeComponent),
      },
      {
        path: 'po',
        canActivate: [commerceGuard],
        loadComponent: () => import('./features/commerce/create-po.component').then((m) => m.CreatePoComponent),
      },
      {
        path: 'orders/:orderId',
        canActivate: [commerceGuard],
        loadComponent: () =>
          import('./features/commerce/order-detail.component').then((m) => m.OrderDetailComponent),
      },
      {
        path: 'orders',
        canActivate: [commerceGuard],
        loadComponent: () => import('./features/commerce/orders.component').then((m) => m.OrdersComponent),
      },
      {
        path: 'gifting',
        redirectTo: 'vouchers',
        pathMatch: 'full',
      },
      {
        path: 'vouchers',
        canActivate: [commerceGuard],
        loadComponent: () => import('./features/commerce/vouchers.component').then((m) => m.VouchersComponent),
      },
      {
        path: 'cards',
        canActivate: [commerceGuard],
        loadComponent: () => import('./features/commerce/cards.component').then((m) => m.CardsComponent),
      },
      {
        path: 'account',
        loadComponent: () => import('./features/account/account-hub.component').then((m) => m.AccountHubComponent),
      },
      {
        path: 'agreement',
        loadComponent: () => import('./features/account/agreement.component').then((m) => m.AgreementComponent),
      },
      {
        path: 'onboarding',
        loadComponent: () =>
          import('./features/onboarding/wizard/onboarding-wizard.component').then((m) => m.OnboardingWizardComponent),
      },
      {
        path: 'business',
        canActivate: [activatedProfileGuard],
        loadComponent: () =>
          import('./features/profile/business-profile.component').then((m) => m.BusinessProfileComponent),
      },
      {
        path: 'bank',
        canActivate: [activatedProfileGuard],
        loadComponent: () => import('./features/profile/bank-profile.component').then((m) => m.BankProfileComponent),
      },
      {
        path: 'documents',
        canActivate: [activatedProfileGuard],
        loadComponent: () =>
          import('./features/profile/documents-profile.component').then((m) => m.DocumentsProfileComponent),
      },
      {
        path: 'settings',
        loadComponent: () =>
          import('./features/console/settings/settings.component').then((m) => m.SettingsComponent),
      },
    ],
  },
  { path: 'admin', redirectTo: 'staff-portal', pathMatch: 'full' },
  { path: 'admin/**', redirectTo: 'staff-portal' },
  { path: 'desk', redirectTo: 'staff-portal', pathMatch: 'full' },
  { path: 'desk/**', redirectTo: 'staff-portal' },
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  { path: '**', redirectTo: 'login' },
];
