import { Injectable, inject } from '@angular/core';
import { delay, Observable, of, throwError } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { DEMO_OTP } from '../validators/india.validators';
import {
  AppDatabase,
  emptyApplication,
  emptyAgreement,
  FulfilmentFile,
  KycApplication,
  Lead,
  LeadStatus,
  MailMessage,
  MerchantAgreement,
  OrderKind,
  OrderMode,
  OrderStatus,
  PartnerOrder,
  PartnerType,
  User,
} from '../models/onboarding.models';
import { StorageService } from './storage.service';
import { authorisationSlotId, enforcePersonaKycFirst, needsAuthSignatoryPersonKyc, needsOwnerPersonKyc } from '../config/entity-rules';
import { appendEvent, generateFilePassword, hydrateOrder, invoiceIdFor, publicOrder, sampleCodes } from '../config/order.util';

const LATENCY = 550;

export interface PartnerSummary {
  user: User;
  application: KycApplication | null;
}

@Injectable({ providedIn: 'root' })
export class MockApiService {
  private readonly storage = inject(StorageService);

  register(payload: {
    fullName: string;
    email: string;
    mobile: string;
    password: string;
    partnerType: Exclude<PartnerType, 'admin' | 'staff'>;
  }): Observable<User> {
    return this.mutate((db) => {
      const email = payload.email.trim().toLowerCase();
      const mobile = payload.mobile.trim();
      if (db.users.some((u) => u.email === email)) {
        throw new Error('An account already exists with this email.');
      }
      if (db.users.some((u) => u.mobile === mobile)) {
        throw new Error('An account already exists with this mobile number.');
      }
      const user: User = {
        id: crypto.randomUUID(),
        fullName: payload.fullName.trim(),
        email,
        mobile,
        password: payload.password,
        partnerType: 'corporate',
        mobileVerified: false,
        emailVerified: false,
        createdAt: new Date().toISOString(),
      };
      db.users.push(user);
      db.applications[user.id] = emptyApplication(user.id);
      this.setSession(db, user.id);
      return user;
    });
  }

  login(identifier: string, password: string): Observable<User> {
    return this.mutate((db) => {
      const key = identifier.trim().toLowerCase();
      const user = db.users.find(
        (u) => u.email === key || u.mobile === identifier.trim(),
      );
      if (!user || user.password !== password) {
        throw new Error('Incorrect email / mobile or password.');
      }
      this.setSession(db, user.id);
      return user;
    });
  }

  logout(): Observable<void> {
    return this.mutate((db) => {
      db.currentToken = null;
    });
  }

  currentUser(): Observable<User | null> {
    const db = this.storage.load();
    const user = this.userFromSession(db);
    return of(user).pipe(delay(80));
  }

  verifyOtp(channel: 'mobile' | 'email', code: string): Observable<User> {
    return this.mutate((db) => {
      const user = this.requireUser(db);
      if (code !== DEMO_OTP) {
        throw new Error('Invalid OTP. Use 123456 in this demo.');
      }
      if (channel === 'mobile') {
        user.mobileVerified = true;
      } else {
        user.emailVerified = true;
      }
      if (user.mobileVerified && user.emailVerified && db.applications[user.id]) {
        const app = db.applications[user.id];
        if (app.status === 'registered' || app.status.startsWith('pending')) {
          app.status = 'draft';
        }
      }
      return { ...user };
    });
  }

  resetPassword(identifier: string, code: string, password: string): Observable<void> {
    return this.mutate((db) => {
      const key = identifier.trim().toLowerCase();
      const user = db.users.find(
        (u) => u.email === key || u.mobile === identifier.trim(),
      );
      if (!user) {
        throw new Error('No account found for that email or mobile.');
      }
      if (code !== DEMO_OTP) {
        throw new Error('Invalid OTP. Use 123456 in this demo.');
      }
      user.password = password;
    });
  }

  getApplication(): Observable<KycApplication> {
    return this.mutate((db) => {
      const user = this.requireUser(db);
      if (user.partnerType !== 'corporate') {
        throw new Error('Partner application is only for corporates.');
      }
      if (!db.applications[user.id]) {
        db.applications[user.id] = emptyApplication(user.id);
      }
      const next = enforcePersonaKycFirst(db.applications[user.id]);
      db.applications[user.id] = next;
      return structuredClone(next);
    }, 180);
  }

  saveDraft(application: KycApplication): Observable<KycApplication> {
    return this.mutate((db) => {
      const user = this.requireUser(db);
      const next = enforcePersonaKycFirst(structuredClone(application));
      next.userId = user.id;
      if (next.status === 'registered') {
        next.status = 'draft';
      }
      db.applications[user.id] = next;
      return structuredClone(next);
    }, 220);
  }

  submitKyc(application: KycApplication): Observable<KycApplication> {
    return this.mutate((db) => {
      const user = this.requireUser(db);
      const next = structuredClone(application);
      next.userId = user.id;
      if (!next.signatory.verified) {
        throw new Error('Complete authorised-signatory KYC before submitting.');
      }
      if (needsOwnerPersonKyc(next) && !next.ownerKyc?.verified) {
        throw new Error('Complete business-owner KYC. The authorised signatory is not an owner of this entity.');
      }
      if (needsAuthSignatoryPersonKyc(next) && !next.authSignatoryKyc?.verified) {
        throw new Error('Complete authorised-signatory KYC before submitting.');
      }
      const authSlot = authorisationSlotId(next.profile.entityType);
      if (authSlot && !next.documents.some((d) => d.slotId === authSlot)) {
        throw new Error('Upload the board resolution or letter of authority appointing the authorised signatory.');
      }
      next.status = 'under_review';
      next.submittedAt = new Date().toISOString();
      db.applications[user.id] = next;
      return structuredClone(next);
    }, 900);
  }

  approveDemo(): Observable<KycApplication> {
    return this.mutate((db) => {
      const user = this.requireUser(db);
      if (user.partnerType === 'admin') {
        throw new Error('Use the admin partners screen to approve KYC / KYB.');
      }
      const app = db.applications[user.id];
      if (!app || app.status !== 'under_review') {
        throw new Error('Nothing is waiting for review.');
      }
      app.status = 'pending_agreement';
      app.kybApprovedAt = new Date().toISOString();
      return structuredClone(app);
    }, 1200);
  }

  signAgreement(payload: MerchantAgreement): Observable<KycApplication> {
    return this.mutate((db) => {
      const user = this.requireUser(db);
      const app = db.applications[user.id];
      if (!app || app.status !== 'pending_agreement') {
        throw new Error('Sign after Payswap admin approves your KYC and KYB.');
      }
      if (!payload.read || !payload.authorised || !payload.eSigned) {
        throw new Error('Read, authorise, and e-sign the agreement.');
      }
      app.agreement = {
        ...emptyAgreement(),
        ...payload,
        signedAt: new Date().toISOString(),
        eSigned: true,
        adminSigned: false,
        adminSignerName: '',
      };
      app.status = 'pending_admin_sign';
      return structuredClone(app);
    }, 900);
  }

  listPartners(): Observable<PartnerSummary[]> {
    return this.mutate((db) => {
      this.requireAdmin(db);
      return db.users
        .filter((u) => u.partnerType === 'corporate')
        .map((user) => ({
          user: structuredClone(user),
          application: db.applications[user.id]
            ? structuredClone(db.applications[user.id])
            : null,
        }));
    }, 300);
  }

  adminApproveKyc(userId: string): Observable<KycApplication> {
    return this.mutate((db) => {
      this.requireAdmin(db);
      const app = db.applications[userId];
      if (!app || app.status !== 'under_review') {
        throw new Error('Partner is not waiting for KYC / KYB review.');
      }
      app.status = 'pending_agreement';
      app.kybApprovedAt = new Date().toISOString();
      return structuredClone(app);
    }, 700);
  }

  adminRejectKyc(userId: string, reason: string): Observable<KycApplication> {
    return this.mutate((db) => {
      this.requireAdmin(db);
      const app = db.applications[userId];
      if (!app || app.status !== 'under_review') {
        throw new Error('Partner is not waiting for KYC / KYB review.');
      }
      app.status = 'draft';
      app.currentStep = 'review';
      app.submittedAt = undefined;
      app.returnReason = reason.trim() || 'Please revise the file and resubmit.';
      return structuredClone(app);
    }, 700);
  }

  adminCountersign(userId: string, adminName: string): Observable<KycApplication> {
    return this.mutate((db) => {
      this.requireAdmin(db);
      const app = db.applications[userId];
      if (!app || app.status !== 'pending_admin_sign' || !app.agreement.eSigned) {
        throw new Error('Partner must e-sign before admin countersign.');
      }
      app.agreement.adminSigned = true;
      app.agreement.adminSignerName = adminName;
      app.agreement.adminSignedAt = new Date().toISOString();
      app.status = 'activated';
      app.activatedAt = app.agreement.adminSignedAt;
      return structuredClone(app);
    }, 800);
  }

  listOrders(forUserId?: string): Observable<PartnerOrder[]> {
    return this.mutate((db) => {
      const user = this.requireUser(db);
      const rows =
        user.partnerType === 'admin'
          ? db.orders
          : user.partnerType === 'staff'
            ? []
            : db.orders.filter((o) => o.userId === (forUserId ?? user.id));
      const admin = user.partnerType === 'admin';
      return structuredClone(rows)
        .map((row) => publicOrder(row, admin))
        .sort((a, b) => +new Date(b.createdAt) - +new Date(a.createdAt));
    }, 250);
  }

  getOrder(orderId: string): Observable<PartnerOrder> {
    return this.mutate((db) => {
      const user = this.requireUser(db);
      const order = db.orders.find((o) => o.id === orderId);
      if (!order) {
        throw new Error('Order not found.');
      }
      if (user.partnerType !== 'admin' && user.partnerType !== 'staff' && order.userId !== user.id) {
        throw new Error('You cannot view this order.');
      }
      if (user.partnerType === 'staff') {
        throw new Error('Staff desk cannot open partner orders.');
      }
      return publicOrder(order, user.partnerType === 'admin');
    }, 200);
  }

  placeOrder(payload: {
    kind: OrderKind;
    title: string;
    brand: string;
    quantity: number;
    unitValue: number;
    note: string;
    mode?: OrderMode;
    poNumber: string;
  }): Observable<PartnerOrder> {
    return this.mutate((db) => {
      const user = this.requireUser(db);
      if (user.partnerType !== 'corporate') {
        throw new Error('Only corporate partners can place orders.');
      }
      const poNumber = payload.poNumber.trim();
      if (!poNumber) {
        throw new Error('Purchase order number is required.');
      }
      const now = new Date().toISOString();
      const live = db.applications[user.id]?.status === 'activated';
      const mode: OrderMode = payload.mode ?? (live ? 'live' : 'test');
      const id = `ord_${crypto.randomUUID().slice(0, 8)}`;
      const order: PartnerOrder = hydrateOrder({
        id,
        userId: user.id,
        kind: payload.kind,
        title: payload.title,
        brand: payload.brand,
        quantity: payload.quantity,
        unitValue: payload.unitValue,
        amount: payload.quantity * payload.unitValue,
        status: 'placed',
        createdAt: now,
        updatedAt: now,
        note: payload.note || (mode === 'test' ? 'Test-mode order' : ''),
        mode,
        timeline: [{ status: 'placed', at: now, note: 'Order received' }],
        invoiceId: invoiceIdFor(id),
        fulfilmentCodes: [],
        legalName: db.applications[user.id]?.profile.legalName || '',
        poNumber,
      });
      db.orders.unshift(order);
      return publicOrder(order, false);
    }, 600);
  }

  partnerCancelOrder(orderId: string): Observable<PartnerOrder> {
    return this.mutate((db) => {
      const user = this.requireUser(db);
      const order = db.orders.find((o) => o.id === orderId);
      if (!order || order.userId !== user.id) {
        throw new Error('Order not found.');
      }
      if (order.status !== 'placed') {
        throw new Error('Only placed orders can be cancelled by the partner.');
      }
      return this.applyStatus(order, 'cancelled', 'Cancelled by partner');
    }, 400);
  }

  adminSetOrderStatus(orderId: string, status: Extract<OrderStatus, 'processing' | 'fulfilled' | 'cancelled'>): Observable<PartnerOrder> {
    return this.mutate((db) => {
      this.requireAdmin(db);
      const order = db.orders.find((o) => o.id === orderId);
      if (!order) {
        throw new Error('Order not found.');
      }
      if (status === 'processing' && order.status !== 'placed') {
        throw new Error('Only placed orders can move to processing.');
      }
      if (status === 'fulfilled' && order.status !== 'placed' && order.status !== 'processing') {
        throw new Error('Only open orders can be fulfilled.');
      }
      if (status === 'cancelled' && order.status !== 'placed' && order.status !== 'processing') {
        throw new Error('This order cannot be cancelled.');
      }
      const note =
        status === 'processing'
          ? 'Payswap started fulfilment'
          : status === 'fulfilled'
            ? 'Codes / cards delivered'
            : 'Cancelled by Payswap admin';
      this.applyStatus(order, status, note);
      if (status === 'fulfilled') {
        order.fulfilmentCodes = sampleCodes(order);
      }
      return structuredClone(order);
    }, 500);
  }

  adminFulfillOrder(orderId: string): Observable<PartnerOrder> {
    return this.adminSetOrderStatus(orderId, 'fulfilled');
  }

  adminFulfillWithFile(orderId: string, file: FulfilmentFile): Observable<PartnerOrder> {
    return this.mutate((db) => {
      this.requireAdmin(db);
      const order = db.orders.find((o) => o.id === orderId);
      if (!order) {
        throw new Error('Order not found.');
      }
      if (order.status !== 'placed' && order.status !== 'processing') {
        throw new Error('Only open orders can be fulfilled with a file.');
      }
      if (order.status === 'placed') {
        this.applyStatus(order, 'processing', 'Payswap started fulfilment');
      }
      const password = generateFilePassword();
      order.fulfilmentFile = file;
      order.filePassword = password;
      this.applyStatus(order, 'fulfilled', 'Password-protected file mailed to partner');
      const partner = db.users.find((u) => u.id === order.userId);
      db.mail = db.mail ?? [];
      db.mail.unshift({
        id: `mail_${crypto.randomUUID().slice(0, 8)}`,
        to: partner?.email || '',
        subject: `Fulfilment file for ${order.poNumber || order.id}`,
        body: `A password-protected voucher / card file is attached (${file.fileName}). Reveal the password in the Payswap order after OTP. The password is not included in this email.`,
        orderId: order.id,
        createdAt: new Date().toISOString(),
        attachmentName: file.fileName,
      });
      if (!order.fulfilmentCodes?.length) {
        order.fulfilmentCodes = sampleCodes(order);
      }
      return publicOrder(order, true);
    }, 650);
  }

  requestFileOtp(orderId: string): Observable<{ sentTo: string }> {
    return this.mutate((db) => {
      const user = this.requireUser(db);
      const order = db.orders.find((o) => o.id === orderId);
      if (!order || order.userId !== user.id) {
        throw new Error('Order not found.');
      }
      if (!order.fulfilmentFile || !order.filePassword) {
        throw new Error('No protected file on this order yet.');
      }
      return { sentTo: user.email };
    }, 300);
  }

  revealFilePassword(
    orderId: string,
    _code: string,
  ): Observable<{ password: string; file: FulfilmentFile }> {
    return this.mutate((db) => {
      const user = this.requireUser(db);
      const order = db.orders.find((o) => o.id === orderId);
      if (!order || order.userId !== user.id) {
        throw new Error('Order not found.');
      }
      if (!order.fulfilmentFile || !order.filePassword) {
        throw new Error('No protected file on this order yet.');
      }
      return { password: order.filePassword, file: structuredClone(order.fulfilmentFile) };
    }, 400);
  }

  listMail(): Observable<MailMessage[]> {
    return this.mutate((db) => {
      this.requireAdmin(db);
      return structuredClone(db.mail ?? []).sort((a, b) => +new Date(b.createdAt) - +new Date(a.createdAt));
    }, 200);
  }

  listTeam(): Observable<User[]> {
    return this.mutate((db) => {
      this.requireAdmin(db);
      return structuredClone(db.users.filter((u) => u.partnerType === 'admin' || u.partnerType === 'staff'));
    }, 200);
  }

  createStaff(payload: { fullName: string; email: string; mobile: string }): Observable<User> {
    return this.mutate((db) => {
      this.requireAdmin(db);
      const email = payload.email.trim().toLowerCase();
      const mobile = payload.mobile.trim();
      if (db.users.some((u) => u.email === email)) {
        throw new Error('An account already exists with this email.');
      }
      if (db.users.some((u) => u.mobile === mobile)) {
        throw new Error('An account already exists with this mobile number.');
      }
      const user: User = {
        id: `user_${crypto.randomUUID().slice(0, 8)}`,
        fullName: payload.fullName.trim(),
        email,
        mobile,
        password: 'Payswap@123',
        partnerType: 'staff',
        mobileVerified: true,
        emailVerified: true,
        createdAt: new Date().toISOString(),
      };
      db.users.push(user);
      return structuredClone(user);
    }, 400);
  }

  listLeads(): Observable<Lead[]> {
    return this.mutate((db) => {
      const user = this.requireDesk(db);
      const rows = db.leads ?? [];
      const visible = user.partnerType === 'admin' ? rows : rows.filter((l) => l.ownerId === user.id);
      return structuredClone(visible).sort((a, b) => +new Date(b.updatedAt) - +new Date(a.updatedAt));
    }, 220);
  }

  getLead(leadId: string): Observable<Lead> {
    return this.mutate((db) => {
      const user = this.requireDesk(db);
      const lead = (db.leads ?? []).find((l) => l.id === leadId);
      if (!lead) {
        throw new Error('Lead not found.');
      }
      if (user.partnerType === 'staff' && lead.ownerId !== user.id) {
        throw new Error('This lead is not assigned to you.');
      }
      return structuredClone(lead);
    }, 180);
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
    return this.mutate((db) => {
      const admin = this.requireAdmin(db);
      const owner = db.users.find((u) => u.id === payload.ownerId && u.partnerType === 'staff');
      if (!owner) {
        throw new Error('Assign the lead to a staff user.');
      }
      const now = new Date().toISOString();
      const lead: Lead = {
        id: `lead_${crypto.randomUUID().slice(0, 8)}`,
        company: payload.company.trim(),
        contactName: payload.contactName.trim(),
        email: payload.email.trim().toLowerCase(),
        mobile: payload.mobile.trim(),
        source: payload.source.trim() || 'Manual',
        valueEstimate: Number(payload.valueEstimate) || 0,
        notes: payload.notes.trim(),
        status: 'new',
        ownerId: owner.id,
        createdAt: now,
        updatedAt: now,
        activity: [{ at: now, userId: admin.id, text: `Lead created and assigned to ${owner.fullName}`, status: 'new' }],
      };
      db.leads = db.leads ?? [];
      db.leads.unshift(lead);
      return structuredClone(lead);
    }, 400);
  }

  updateLead(
    leadId: string,
    patch: { status?: LeadStatus; notes?: string; ownerId?: string; activityText?: string },
  ): Observable<Lead> {
    return this.mutate((db) => {
      const user = this.requireDesk(db);
      const lead = (db.leads ?? []).find((l) => l.id === leadId);
      if (!lead) {
        throw new Error('Lead not found.');
      }
      if (user.partnerType === 'staff' && lead.ownerId !== user.id) {
        throw new Error('This lead is not assigned to you.');
      }
      if (patch.ownerId && user.partnerType !== 'admin') {
        throw new Error('Only admin can reassign leads.');
      }
      const now = new Date().toISOString();
      if (patch.ownerId) {
        const owner = db.users.find((u) => u.id === patch.ownerId && u.partnerType === 'staff');
        if (!owner) {
          throw new Error('Staff owner not found.');
        }
        lead.ownerId = owner.id;
        lead.activity.push({ at: now, userId: user.id, text: `Reassigned to ${owner.fullName}` });
      }
      if (patch.status && patch.status !== lead.status) {
        lead.status = patch.status;
        lead.activity.push({ at: now, userId: user.id, text: `Status → ${patch.status}`, status: patch.status });
      }
      if (patch.notes !== undefined) {
        lead.notes = patch.notes;
      }
      if (patch.activityText?.trim()) {
        lead.activity.push({ at: now, userId: user.id, text: patch.activityText.trim() });
      }
      lead.updatedAt = now;
      return structuredClone(lead);
    }, 350);
  }

  private applyStatus(order: PartnerOrder, status: OrderStatus, note: string): PartnerOrder {
    const base = hydrateOrder(order);
    base.status = status;
    base.updatedAt = new Date().toISOString();
    base.timeline = appendEvent(base, status, note);
    if (status === 'cancelled') {
      base.fulfilmentCodes = [];
    }
    Object.assign(order, base);
    return structuredClone(order);
  }

  private mutate<T>(work: (db: AppDatabase) => T, ms = LATENCY): Observable<T> {
    return of(null).pipe(
      delay(ms),
      switchMap(() => {
        try {
          const db = this.storage.load();
          const result = work(db);
          this.storage.save(db);
          return of(result);
        } catch (err) {
          return throwError(() => err);
        }
      }),
    );
  }

  private setSession(db: AppDatabase, userId: string): void {
    const token = crypto.randomUUID();
    db.sessions = db.sessions.filter((s) => s.userId !== userId);
    db.sessions.push({ token, userId });
    db.currentToken = token;
  }

  private userFromSession(db: AppDatabase): User | null {
    if (!db.currentToken) {
      return null;
    }
    const session = db.sessions.find((s) => s.token === db.currentToken);
    if (!session) {
      return null;
    }
    return db.users.find((u) => u.id === session.userId) ?? null;
  }

  private requireUser(db: AppDatabase): User {
    const user = this.userFromSession(db);
    if (!user) {
      throw new Error('Please sign in again.');
    }
    return user;
  }

  private requireDesk(db: AppDatabase): User {
    const user = this.requireUser(db);
    if (user.partnerType !== 'admin' && user.partnerType !== 'staff') {
      throw new Error('Lead desk access required.');
    }
    return user;
  }

  private requireAdmin(db: AppDatabase): User {
    const user = this.requireUser(db);
    if (user.partnerType !== 'admin') {
      throw new Error('Admin access required.');
    }
    return user;
  }
}
