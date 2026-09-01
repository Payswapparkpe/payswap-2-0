import { inject, Injectable, signal } from '@angular/core';
import { Observable, tap, catchError, throwError } from 'rxjs';
import { map, switchMap } from 'rxjs/operators';
import {
  CatalogItem,
  FulfilmentFile,
  KycApplication,
  Lead,
  LeadStatus,
  MailMessage,
  MerchantAgreement,
  OnboardingStep,
  OrderKind,
  PartnerOrder,
  User,
} from '../models/onboarding.models';
import { ApiService } from './api.service';
import { MockApiService, PartnerSummary } from './mock-api.service';
import { OtpService } from './otp.service';

@Injectable({ providedIn: 'root' })
export class OnboardingService {
  private readonly api = inject(ApiService);
  private readonly mock = inject(MockApiService);
  private readonly otp = inject(OtpService);

  readonly application = signal<KycApplication | null>(null);
  readonly saving = signal(false);
  readonly orders = signal<PartnerOrder[]>([]);
  readonly catalog = signal<CatalogItem[]>([]);
  readonly partners = signal<PartnerSummary[]>([]);
  readonly mail = signal<MailMessage[]>([]);
  readonly leads = signal<Lead[]>([]);
  readonly team = signal<User[]>([]);

  load(): Observable<KycApplication> {
    return this.api.get<KycApplication>('/merchant/onboarding/').pipe(tap((app) => this.application.set(app)));
  }

  save(application: KycApplication): Observable<KycApplication> {
    const completedStep = this.application()?.currentStep;
    this.saving.set(true);
    this.application.set(application);
    const payload =
      completedStep && completedStep !== application.currentStep
        ? { ...application, step: completedStep }
        : application;
    return this.api.putJson<KycApplication>('/merchant/onboarding/', payload).pipe(
      tap((app) => {
        this.application.set(app);
        this.saving.set(false);
      }),
      catchError((err) => {
        this.saving.set(false);
        if (completedStep) {
          this.load().subscribe();
        }
        return throwError(() => err);
      }),
    );
  }

  patch(partial: Partial<KycApplication>): Observable<KycApplication> {
    const current = this.application();
    if (!current) {
      throw new Error('Application not loaded');
    }
    return this.save({ ...current, ...partial });
  }

  goTo(step: OnboardingStep): Observable<KycApplication> {
    return this.patch({ currentStep: step });
  }

  navigateStep(step: OnboardingStep): void {
    const current = this.application();
    if (!current) {
      return;
    }
    this.application.set({ ...current, currentStep: step });
  }

  submit(): Observable<KycApplication> {
    this.saving.set(true);
    return this.api.postJson<KycApplication>('/merchant/onboarding/submit', { confirmed: true }).pipe(
      tap((app) => {
        this.application.set(app);
        this.saving.set(false);
      }),
    );
  }

  signAgreement(_payload: MerchantAgreement): Observable<KycApplication> {
    return this.api.postJson<KycApplication>('/merchant/agreements/', { action: 'start_esign' }).pipe(
      tap((app) => this.application.set(app)),
    );
  }

  loadCatalog(): Observable<CatalogItem[]> {
    return this.api.get<{ items: CatalogItem[] }>('/merchant/catalog/').pipe(
      map((res) => res.items),
      tap((items) => this.catalog.set(items)),
    );
  }

  loadOrders(): Observable<PartnerOrder[]> {
    return this.api.get<{ orders: PartnerOrder[] }>('/merchant/orders/').pipe(
      map((res) => res.orders),
      tap((rows) => this.orders.set(rows)),
    );
  }

  getOrder(orderId: string): Observable<PartnerOrder> {
    return this.api.get<{ order: PartnerOrder }>(`/merchant/orders/${orderId}/`).pipe(map((res) => res.order));
  }

  placeOrder(payload: {
    kind: OrderKind;
    title: string;
    brand: string;
    quantity: number;
    unitValue: number;
    note: string;
    mode?: 'test' | 'live';
    poNumber: string;
    productId?: string | number;
  }): Observable<PartnerOrder> {
    const productId = payload.productId ?? payload.brand;
    return this.api
      .postJson<{ order: PartnerOrder }>('/merchant/orders/', {
        productId,
        quantity: payload.quantity,
        submit: true,
        note: payload.note,
        poNumber: payload.poNumber,
      })
      .pipe(
        map((res) => res.order),
        tap((order) => this.orders.update((rows) => [order, ...rows])),
      );
  }

  cancelOrder(orderId: string): Observable<PartnerOrder> {
    return this.api
      .postJson<{ order: PartnerOrder }>(`/merchant/orders/${orderId}/`, { action: 'cancel' })
      .pipe(
        map((res) => res.order),
        tap((order) => this.orders.update((rows) => rows.map((r) => (r.id === order.id ? order : r)))),
      );
  }

  approveDemo(): Observable<KycApplication> {
    return this.mock.approveDemo().pipe(tap((app) => this.application.set(app)));
  }

  loadPartners(): Observable<PartnerSummary[]> {
    return this.mock.listPartners().pipe(tap((rows) => this.partners.set(rows)));
  }

  adminApproveKyc(userId: string): Observable<KycApplication> {
    return this.mock.adminApproveKyc(userId).pipe(tap(() => this.loadPartners().subscribe()));
  }

  adminRejectKyc(userId: string, reason: string): Observable<KycApplication> {
    return this.mock.adminRejectKyc(userId, reason).pipe(tap(() => this.loadPartners().subscribe()));
  }

  adminCountersign(userId: string, adminName: string): Observable<KycApplication> {
    return this.mock.adminCountersign(userId, adminName).pipe(tap(() => this.loadPartners().subscribe()));
  }

  adminFulfillOrder(orderId: string): Observable<PartnerOrder> {
    return this.adminSetOrderStatus(orderId, 'fulfilled');
  }

  adminSetOrderStatus(
    orderId: string,
    status: 'processing' | 'fulfilled' | 'cancelled',
  ): Observable<PartnerOrder> {
    return this.mock.adminSetOrderStatus(orderId, status).pipe(
      tap((order) => this.orders.update((rows) => rows.map((r) => (r.id === order.id ? order : r)))),
    );
  }

  fulfillWithFile(orderId: string, file: FulfilmentFile): Observable<PartnerOrder> {
    return this.mock.adminFulfillWithFile(orderId, file).pipe(
      tap((order) => this.orders.update((rows) => rows.map((r) => (r.id === order.id ? order : r)))),
    );
  }

  requestFileOtp(orderId: string): Observable<{ sentTo: string }> {
    return this.otp.sendSecurityOtp('email').pipe(
      map(() => ({ sentTo: 'your registered email' })),
    );
  }

  revealFilePassword(orderId: string, code: string): Observable<{ password: string; file: FulfilmentFile }> {
    return this.otp.confirmSecurityOtp('email', code).pipe(
      switchMap(() => this.mock.revealFilePassword(orderId, code)),
    );
  }

  loadMail(): Observable<MailMessage[]> {
    return this.mock.listMail().pipe(tap((rows) => this.mail.set(rows)));
  }

  loadTeam(): Observable<User[]> {
    return this.mock.listTeam().pipe(tap((rows) => this.team.set(rows)));
  }

  createStaff(payload: { fullName: string; email: string; mobile: string }): Observable<User> {
    return this.mock.createStaff(payload).pipe(tap((user) => this.team.update((rows) => [...rows, user])));
  }

  loadLeads(): Observable<Lead[]> {
    return this.mock.listLeads().pipe(tap((rows) => this.leads.set(rows)));
  }

  getLead(leadId: string): Observable<Lead> {
    return this.mock.getLead(leadId);
  }

  createLead(payload: {
    company: string;
    contactName: string;
    email: string;
    mobile: string;
    source: string;
    valueEstimate: number;
    notes: string;
    ownerId: string;
  }): Observable<Lead> {
    return this.mock.createLead(payload).pipe(tap((lead) => this.leads.update((rows) => [lead, ...rows])));
  }

  updateLead(
    leadId: string,
    patch: { status?: LeadStatus; notes?: string; ownerId?: string; activityText?: string },
  ): Observable<Lead> {
    return this.mock.updateLead(leadId, patch).pipe(
      tap((lead) => this.leads.update((rows) => rows.map((r) => (r.id === lead.id ? lead : r)))),
    );
  }
}
