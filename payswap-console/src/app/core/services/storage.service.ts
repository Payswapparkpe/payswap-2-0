import { Injectable } from '@angular/core';
import { hydrateOrder } from '../config/order.util';
import {
  AppDatabase,
  emptyAddress,
  emptyAgreement,
  emptyApplication,
  emptyPersonKyc,
  Lead,
  MailMessage,
  PartnerOrder,
  Session,
  User,
} from '../models/onboarding.models';

const STORAGE_KEY = 'payswap-console-db-v5';

@Injectable({ providedIn: 'root' })
export class StorageService {
  load(): AppDatabase {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      const seeded = this.seed();
      this.save(seeded);
      return seeded;
    }
    try {
      return this.normalize(JSON.parse(raw) as AppDatabase);
    } catch {
      const seeded = this.seed();
      this.save(seeded);
      return seeded;
    }
  }

  save(db: AppDatabase): void {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(db));
  }

  reset(): AppDatabase {
    const seeded = this.seed();
    this.save(seeded);
    return seeded;
  }

  private normalize(db: AppDatabase): AppDatabase {
    db.orders = (db.orders ?? []).map((row) => hydrateOrder(row));
    db.mail = db.mail ?? [];
    db.leads = db.leads ?? [];
    Object.values(db.applications ?? {}).forEach((app) => {
      if (!app.agreement) {
        app.agreement = emptyAgreement();
      }
      if (app.agreement.adminSigned === undefined) {
        app.agreement.adminSigned = false;
        app.agreement.adminSignerName = '';
      }
      if (app.signatoryIsOwner === undefined) {
        app.signatoryIsOwner = null;
      }
      if (!app.ownerKyc) {
        app.ownerKyc = emptyPersonKyc();
      }
      if (!app.authSignatoryKyc) {
        app.authSignatoryKyc = emptyPersonKyc();
      }
      if (!app.registryMembers) {
        app.registryMembers = [];
      }
      if (app.kycPersonIsAuthorisedSignatory === undefined) {
        app.kycPersonIsAuthorisedSignatory = null;
      }
      if (app.signatoryRelation === undefined) {
        app.signatoryRelation = '';
      }
      if (app.authorisedSignatoryName === undefined) {
        app.authorisedSignatoryName = '';
      }
      if (!app.profile.gstinOptions) {
        app.profile.gstinOptions = [];
      }
      const signatory = app.signatory as typeof app.signatory & { ckycFailed?: boolean };
      if (signatory.ckycFailed !== undefined) {
        signatory.digilockerFailed = signatory.digilockerFailed || !!signatory.ckycFailed;
        delete signatory.ckycFailed;
      }
      if (signatory.digilockerFailed === undefined) {
        signatory.digilockerFailed = false;
      }
      if (signatory.path && signatory.path !== 'digilocker') {
        signatory.path = 'digilocker';
      }
      app.ubos?.forEach((ubo) => {
        if (ubo.kycPath && ubo.kycPath !== 'digilocker') {
          ubo.kycPath = 'digilocker';
        }
      });
    });
    db.users.forEach((user) => {
      if (!user.partnerType || (user.partnerType as string) === 'reseller') {
        user.partnerType = user.email.includes('admin') ? 'admin' : 'corporate';
      }
    });
    return db;
  }

  private seed(): AppDatabase {
    const admin: User = {
      id: 'user-admin',
      fullName: 'Payswap Admin',
      email: 'admin@payswap.in',
      mobile: '9999900001',
      password: 'Payswap@123',
      partnerType: 'admin',
      mobileVerified: true,
      emailVerified: true,
      createdAt: '2026-01-01T08:00:00.000Z',
    };

    const user: User = {
      id: 'user-acme',
      fullName: 'Priya Sharma',
      email: 'priya@acme.in',
      mobile: '9876543210',
      password: 'Payswap@123',
      partnerType: 'corporate',
      mobileVerified: true,
      emailVerified: true,
      createdAt: '2026-04-12T08:00:00.000Z',
    };

    const giftmart: User = {
      id: 'user-giftmart',
      fullName: 'Rohit Verma',
      email: 'rohit@giftmart.in',
      mobile: '9988776655',
      password: 'Payswap@123',
      partnerType: 'corporate',
      mobileVerified: true,
      emailVerified: true,
      createdAt: '2026-05-02T08:00:00.000Z',
    };

    const application = emptyApplication(user.id);
    application.status = 'draft';
    application.currentStep = 'signatory';
    application.profile = {
      brandName: 'Acme Pay',
      legalName: 'Acme Technologies Private Limited',
      entityType: 'private_limited',
      category: 'gifting',
      subCategory: 'prepaid_cards',
      website: 'https://acme.in',
      monthlyVolume: '10l_1cr',
      gstin: '29AAACP1234C1Z5',
      noGstin: false,
    };
    application.identity = {
      pan: 'AAACP1234C',
      doi: '2019-04-12',
      cin: 'U72900KA2019PTC123456',
      llpin: '',
      sameAsRegistered: true,
      registeredAddress: {
        line1: '12, Residency Road',
        line2: 'Shanthala Nagar',
        city: 'Bengaluru',
        state: 'Karnataka',
        pin: '560025',
      },
      operatingAddress: emptyAddress(),
      panCheck: null,
      gstinCheck: null,
      cinCheck: null,
    };
    application.signatory = {
      name: 'Priya Sharma',
      pan: 'AAJPS1234P',
      dob: '1990-06-18',
      mobile: '9876543210',
      path: 'digilocker',
      verified: false,
      digilockerFailed: false,
      digilocker: null,
      address: emptyAddress(),
      docs: [],
    };
    application.signatoryIsOwner = null;

    const giftmartApp = emptyApplication(giftmart.id);
    giftmartApp.status = 'under_review';
    giftmartApp.currentStep = 'review';
    giftmartApp.submittedAt = '2026-08-18T10:00:00.000Z';
    giftmartApp.profile = {
      brandName: 'GiftMart',
      legalName: 'GiftMart Retail Private Limited',
      entityType: 'private_limited',
      category: 'gifting',
      subCategory: 'brand_vouchers',
      website: 'https://giftmart.in',
      monthlyVolume: '10l_1cr',
      gstin: '27AABCG9988D1Z2',
      noGstin: false,
    };
    giftmartApp.identity = {
      pan: 'AABCG9988D',
      doi: '2018-01-10',
      cin: 'U52100MH2018PTC998877',
      llpin: '',
      sameAsRegistered: true,
      registeredAddress: {
        line1: '41, Linking Road',
        line2: '',
        city: 'Mumbai',
        state: 'Maharashtra',
        pin: '400050',
      },
      operatingAddress: emptyAddress(),
      panCheck: {
        verificationId: 'ver_gm_pan',
        referenceId: 41001,
        status: 'VALID',
        registeredName: 'GiftMart Retail Private Limited',
      },
      gstinCheck: {
        verificationId: 'ver_gm_gst',
        referenceId: 41002,
        status: 'VALID',
        registeredName: 'GiftMart Retail Private Limited',
      },
      cinCheck: {
        verificationId: 'ver_gm_cin',
        referenceId: 41003,
        status: 'VALID',
        registeredName: 'GiftMart Retail Private Limited',
      },
    };
    giftmartApp.signatory = {
      name: 'Rohit Verma',
      pan: 'AAJPV4455R',
      dob: '1988-03-12',
      mobile: '9988776655',
      path: 'digilocker',
      verified: true,
      digilockerFailed: false,
      digilocker: {
        verificationId: 'ver_gm_dl',
        referenceId: 41004,
        status: 'AUTHENTICATED',
        documents: [
          { type: 'PAN', name: 'Rohit Verma', idMasked: 'XXXXX4455R' },
          { type: 'AADHAAR', name: 'Rohit Verma', idMasked: 'XXXXXXXX1234' },
          { type: 'DRIVING_LICENSE', name: 'Rohit Verma', idMasked: 'MH01********4455' },
        ],
      },
      address: emptyAddress(),
      docs: [
        { slotId: 'signatory_pan', fileName: 'rohit-pan.pdf', fileSize: 180000, mimeType: 'application/pdf' },
        { slotId: 'signatory_id', fileName: 'rohit-aadhaar.pdf', fileSize: 210000, mimeType: 'application/pdf' },
      ],
    };
    giftmartApp.signatoryIsOwner = true;
    giftmartApp.ubos = [
      {
        id: 'ubo-rohit',
        name: 'Rohit Verma',
        pan: 'AAJPV4455R',
        ownershipPercent: 60,
        relationship: 'Director',
        kycPath: 'digilocker',
        kycVerified: true,
      },
    ];
    giftmartApp.documents = [
      { slotId: 'company_pan', fileName: 'giftmart-pan.pdf', fileSize: 160000, mimeType: 'application/pdf' },
      { slotId: 'coi', fileName: 'giftmart-coi.pdf', fileSize: 240000, mimeType: 'application/pdf' },
      { slotId: 'moa', fileName: 'giftmart-moa.pdf', fileSize: 320000, mimeType: 'application/pdf' },
      { slotId: 'aoa', fileName: 'giftmart-aoa.pdf', fileSize: 280000, mimeType: 'application/pdf' },
      { slotId: 'board_resolution', fileName: 'giftmart-br.pdf', fileSize: 90000, mimeType: 'application/pdf' },
      { slotId: 'gst_certificate', fileName: 'giftmart-gst.pdf', fileSize: 140000, mimeType: 'application/pdf' },
      { slotId: 'bank_proof', fileName: 'giftmart-cheque.pdf', fileSize: 110000, mimeType: 'application/pdf' },
    ];
    giftmartApp.ubosFrozen = true;
    giftmartApp.bank = {
      accountNumber: '501002345678',
      ifsc: 'HDFC0001234',
      holderName: 'GiftMart Retail Private Limited',
      accountType: 'current',
      bankName: 'HDFC Bank',
      branch: 'Koramangala, Bengaluru',
      pennyDropStatus: 'matched',
    };
    giftmartApp.compliance = {
      ...giftmartApp.compliance,
      authorisedDeclaration: true,
      truthDeclaration: true,
      dpdpConsent: true,
    };

    const orders: PartnerOrder[] = [
      hydrateOrder({
        id: 'ord_gift_101',
        userId: user.id,
        kind: 'corporate_gifting',
        title: 'Diwali employee gift pack',
        brand: 'Mixed brands',
        quantity: 250,
        unitValue: 1000,
        amount: 250000,
        status: 'processing',
        createdAt: '2026-08-19T09:30:00.000Z',
        note: 'Ship codes by 25 Aug',
        legalName: application.profile.legalName,
        poNumber: 'PO-ACME-101',
      } as PartnerOrder),
      hydrateOrder({
        id: 'ord_vch_88',
        userId: giftmart.id,
        kind: 'brand_voucher',
        title: 'Amazon Pay gift cards',
        brand: 'Amazon',
        quantity: 500,
        unitValue: 500,
        amount: 250000,
        status: 'placed',
        createdAt: '2026-08-20T14:10:00.000Z',
        note: 'Festival voucher restock',
        legalName: giftmartApp.profile.legalName,
        poNumber: 'PO-GM-2208',
      } as PartnerOrder),
      hydrateOrder({
        id: 'ord_card_12',
        userId: user.id,
        kind: 'prepaid_card',
        title: 'Meal card load · Q2',
        brand: 'Payswap Meal',
        quantity: 120,
        unitValue: 2000,
        amount: 240000,
        status: 'fulfilled',
        createdAt: '2026-08-12T11:00:00.000Z',
        note: '',
        legalName: application.profile.legalName,
        poNumber: 'PO-ACME-088',
      } as PartnerOrder),
    ];

    const staff: User = {
      id: 'user-leads',
      fullName: 'Ananya Joshi',
      email: 'leads@payswap.in',
      mobile: '9999900002',
      password: 'Payswap@123',
      partnerType: 'staff',
      mobileVerified: true,
      emailVerified: true,
      createdAt: '2026-06-01T08:00:00.000Z',
    };

    const now = '2026-08-28T10:00:00.000Z';
    const leads: Lead[] = [
      {
        id: 'lead_gm_1',
        company: 'GiftMart Retail Private Limited',
        contactName: 'Rohit Verma',
        email: 'rohit@giftmart.in',
        mobile: '9988776655',
        source: 'Inbound',
        valueEstimate: 2500000,
        notes: 'Already submitted KYB. Follow up on first live PO.',
        status: 'kyc',
        ownerId: staff.id,
        partnerUserId: giftmart.id,
        createdAt: '2026-08-10T09:00:00.000Z',
        updatedAt: now,
        activity: [
          { at: '2026-08-10T09:00:00.000Z', userId: admin.id, text: 'Lead created from inbound form', status: 'new' },
          { at: now, userId: staff.id, text: 'KYB file under admin review', status: 'kyc' },
        ],
      },
      {
        id: 'lead_new_2',
        company: 'Northwind Foods',
        contactName: 'Meera Iyer',
        email: 'meera@northwind.example',
        mobile: '9811100110',
        source: 'Manual',
        valueEstimate: 800000,
        notes: 'Meal cards for 400 staff.',
        status: 'contacted',
        ownerId: staff.id,
        createdAt: '2026-08-22T11:00:00.000Z',
        updatedAt: '2026-08-25T08:00:00.000Z',
        activity: [
          { at: '2026-08-22T11:00:00.000Z', userId: admin.id, text: 'Manual lead from sales call', status: 'new' },
          { at: '2026-08-25T08:00:00.000Z', userId: staff.id, text: 'Intro call done. Sending commercial sheet.', status: 'contacted' },
        ],
      },
      {
        id: 'lead_new_3',
        company: 'Orbit Logistics',
        contactName: 'Kabir Shah',
        email: 'kabir@orbit.example',
        mobile: '9822200220',
        source: 'Referral',
        valueEstimate: 1200000,
        notes: 'Brand vouchers for driver incentives.',
        status: 'new',
        ownerId: staff.id,
        createdAt: '2026-08-27T14:00:00.000Z',
        updatedAt: '2026-08-27T14:00:00.000Z',
        activity: [{ at: '2026-08-27T14:00:00.000Z', userId: admin.id, text: 'Assigned to Ananya', status: 'new' }],
      },
    ];

    const mail: MailMessage[] = [];

    const session: Session = { token: 'session-acme', userId: user.id };

    return {
      users: [admin, user, giftmart, staff],
      sessions: [session],
      applications: {
        [user.id]: application,
        [giftmart.id]: giftmartApp,
      },
      orders,
      mail,
      leads,
      currentToken: null,
    };
  }
}
