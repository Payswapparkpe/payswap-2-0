import { inject, Injectable, signal } from '@angular/core';
import { Observable, tap, catchError, throwError } from 'rxjs';
import { map } from 'rxjs/operators';
import {
  CatalogItem,
  KycApplication,
  MerchantAgreement,
  OnboardingStep,
  OrderKind,
  PartnerOrder,
} from '../models/onboarding.models';
import { ApiService } from './api.service';

@Injectable({ providedIn: 'root' })
export class OnboardingService {
  private readonly api = inject(ApiService);

  readonly application = signal<KycApplication | null>(null);
  readonly saving = signal(false);
  readonly orders = signal<PartnerOrder[]>([]);
  readonly catalog = signal<CatalogItem[]>([]);

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

}
