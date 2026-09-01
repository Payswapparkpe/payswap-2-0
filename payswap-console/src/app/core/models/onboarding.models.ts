export type EntityType =
  | 'individual'
  | 'proprietorship'
  | 'partnership'
  | 'llp'
  | 'private_limited'
  | 'public_limited'
  | 'opc'
  | 'trust_society_ngo'
  | 'huf';

export type PartnerType = 'corporate' | 'admin' | 'staff';

export type AccountStatus =
  | 'pending_mobile_otp'
  | 'pending_email_otp'
  | 'registered'
  | 'draft'
  | 'under_review'
  | 'pending_agreement'
  | 'pending_admin_sign'
  | 'activated';

export type SignatoryKycPath = 'digilocker';

export type OnboardingStep =
  | 'signatory'
  | 'profile'
  | 'owner'
  | 'identity'
  | 'ubo'
  | 'bank'
  | 'documents'
  | 'review';

export type AccountType = 'current' | 'savings';

export interface GstinOption {
  gstin: string;
  state: string;
  status: string;
  legalName: string;
}

export type PennyDropStatus = 'idle' | 'sent' | 'matched' | 'mismatch';

export interface User {
  id: string;
  fullName: string;
  email: string;
  mobile: string;
  password: string;
  partnerType: PartnerType;
  mobileVerified: boolean;
  emailVerified: boolean;
  createdAt: string;
}

export interface Address {
  line1: string;
  line2: string;
  city: string;
  state: string;
  pin: string;
}

export interface Ubo {
  id: string;
  name: string;
  pan: string;
  ownershipPercent: number;
  relationship: string;
  kycPath?: SignatoryKycPath;
  kycVerified: boolean;
}

export interface RegistryCheck {
  verificationId: string;
  referenceId: number;
  status: string;
  registeredName: string;
}

export interface DigilockerSnapshot {
  verificationId: string;
  referenceId: number;
  status: string;
  documents: Array<{ type: string; name: string; idMasked: string }>;
}

export interface UploadedDoc {
  slotId: string;
  fileName: string;
  fileSize: number;
  mimeType: string;
  /** Present for files uploaded in this browser session; demo seeds may omit it. */
  dataUrl?: string;
}

export interface BankDetails {
  accountNumber: string;
  ifsc: string;
  holderName: string;
  accountType: AccountType;
  bankName: string;
  branch: string;
  pennyDropStatus: PennyDropStatus;
  proofFile?: UploadedDoc;
}

export interface SignatoryKyc {
  name: string;
  pan: string;
  dob: string;
  mobile: string;
  path?: SignatoryKycPath;
  verified: boolean;
  digilockerFailed: boolean;
  digilocker?: DigilockerSnapshot | null;
  address: Address;
  docs: UploadedDoc[];
}

export interface BusinessProfile {
  brandName: string;
  legalName: string;
  entityType: EntityType | '';
  category: string;
  subCategory: string;
  website: string;
  monthlyVolume: string;
  gstin: string;
  noGstin: boolean;
  gstinOptions?: GstinOption[];
}

export interface BusinessIdentity {
  pan: string;
  doi: string;
  cin: string;
  llpin: string;
  registeredAddress: Address;
  operatingAddress: Address;
  sameAsRegistered: boolean;
  panCheck?: RegistryCheck | null;
  gstinCheck?: RegistryCheck | null;
  cinCheck?: RegistryCheck | null;
  gstinOptions?: GstinOption[];
}

export interface Compliance {
  privacyPolicy: boolean;
  refundPolicy: boolean;
  terms: boolean;
  physicalAddress: boolean;
  authorisedDeclaration: boolean;
  truthDeclaration: boolean;
  dpdpConsent: boolean;
}

export interface MerchantAgreement {
  read: boolean;
  authorised: boolean;
  eSigned: boolean;
  signerName: string;
  signedAt?: string;
  adminSigned: boolean;
  adminSignerName: string;
  adminSignedAt?: string;
}

export type OrderKind = 'corporate_gifting' | 'brand_voucher' | 'prepaid_card';
export type OrderStatus = 'draft' | 'placed' | 'processing' | 'fulfilled' | 'cancelled';
export type OrderMode = 'test' | 'live';

export interface OrderEvent {
  status: OrderStatus;
  at: string;
  note: string;
}

export interface CatalogItem {
  id: string;
  brand: string;
  title: string;
  kind: OrderKind;
  denominations: number[];
  category: string;
  logo: string;
  accent: string;
}

export interface FulfilmentFile {
  fileName: string;
  mimeType: string;
  dataUrl: string;
}

export interface PartnerOrder {
  id: string;
  userId: string;
  kind: OrderKind;
  title: string;
  brand: string;
  quantity: number;
  unitValue: number;
  amount: number;
  status: OrderStatus;
  createdAt: string;
  updatedAt: string;
  note: string;
  mode: OrderMode;
  timeline: OrderEvent[];
  invoiceId: string;
  fulfilmentCodes: string[];
  legalName: string;
  poNumber: string;
  fulfilmentFile?: FulfilmentFile;
  filePassword?: string;
}

export interface MailMessage {
  id: string;
  to: string;
  subject: string;
  body: string;
  orderId: string;
  createdAt: string;
  attachmentName?: string;
}

export type LeadStatus = 'new' | 'contacted' | 'qualified' | 'kyc' | 'commercial' | 'won' | 'lost';

export interface LeadActivity {
  at: string;
  userId: string;
  text: string;
  status?: LeadStatus;
}

export interface Lead {
  id: string;
  company: string;
  contactName: string;
  email: string;
  mobile: string;
  source: string;
  valueEstimate: number;
  notes: string;
  status: LeadStatus;
  ownerId: string;
  partnerUserId?: string;
  createdAt: string;
  updatedAt: string;
  activity: LeadActivity[];
}

export interface KycApplication {
  userId: string;
  status: AccountStatus;
  currentStep: OnboardingStep;
  profile: BusinessProfile;
  identity: BusinessIdentity;
  signatory: SignatoryKyc;
  /** Whether the person completing KYC is also the authorised signatory. */
  kycPersonIsAuthorisedSignatory: boolean | null;
  /** Authorised signatory’s relation to the entity (director, partner, etc.). */
  signatoryRelation: string;
  /** Used when the KYC person is not the authorised signatory. */
  authorisedSignatoryName: string;
  /** null until answered on entities where owner can differ from signatory. */
  signatoryIsOwner: boolean | null;
  /** Person KYC of a business owner / director when the signatory is not an owner. */
  ownerKyc: SignatoryKyc;
  ubos: Ubo[];
  /** Last admin send-back note, if any. */
  returnReason?: string;
  ubosFrozen: boolean;
  publicListedSkip: boolean;
  bank: BankDetails;
  documents: UploadedDoc[];
  compliance: Compliance;
  agreement: MerchantAgreement;
  submittedAt?: string;
  kybApprovedAt?: string;
  activatedAt?: string;
}

export interface Session {
  token: string;
  userId: string;
}

export interface AppDatabase {
  users: User[];
  sessions: Session[];
  applications: Record<string, KycApplication>;
  orders: PartnerOrder[];
  mail: MailMessage[];
  leads: Lead[];
  currentToken: string | null;
}

export const ONBOARDING_STEPS: { id: OnboardingStep; label: string }[] = [
  { id: 'signatory', label: 'KYC' },
  { id: 'profile', label: 'Business' },
  { id: 'owner', label: 'Owner KYC' },
  { id: 'identity', label: 'KYB' },
  { id: 'ubo', label: 'Owners' },
  { id: 'bank', label: 'Bank' },
  { id: 'documents', label: 'Documents' },
  { id: 'review', label: 'Review' },
];

export const ENTITY_LABELS: Record<EntityType, string> = {
  individual: 'Individual / Unregistered',
  proprietorship: 'Sole Proprietorship',
  partnership: 'Partnership',
  llp: 'Limited Liability Partnership',
  private_limited: 'Private Limited Company',
  public_limited: 'Public Limited Company',
  opc: 'One Person Company',
  trust_society_ngo: 'Trust / Society / NGO',
  huf: 'Hindu Undivided Family',
};

export function emptyAddress(): Address {
  return { line1: '', line2: '', city: '', state: '', pin: '' };
}

export function emptyPersonKyc(): SignatoryKyc {
  return {
    name: '',
    pan: '',
    dob: '',
    mobile: '',
    path: 'digilocker',
    verified: false,
    digilockerFailed: false,
    digilocker: null,
    address: emptyAddress(),
    docs: [],
  };
}

export function emptyApplication(userId: string): KycApplication {
  return {
    userId,
    status: 'registered',
    currentStep: 'signatory',
    profile: {
      brandName: '',
      legalName: '',
      entityType: '',
      category: '',
      subCategory: '',
      website: '',
      monthlyVolume: '',
      gstin: '',
      noGstin: false,
      gstinOptions: [],
    },
    identity: {
      pan: '',
      doi: '',
      cin: '',
      llpin: '',
      registeredAddress: emptyAddress(),
      operatingAddress: emptyAddress(),
      sameAsRegistered: true,
      panCheck: null,
      gstinCheck: null,
      cinCheck: null,
    },
    signatory: emptyPersonKyc(),
    kycPersonIsAuthorisedSignatory: null,
    signatoryRelation: '',
    authorisedSignatoryName: '',
    signatoryIsOwner: null,
    ownerKyc: emptyPersonKyc(),
    ubos: [],
    ubosFrozen: false,
    publicListedSkip: false,
    bank: {
      accountNumber: '',
      ifsc: '',
      holderName: '',
      accountType: 'current',
      bankName: '',
      branch: '',
      pennyDropStatus: 'idle',
    },
    documents: [],
    compliance: {
      privacyPolicy: false,
      refundPolicy: false,
      terms: false,
      physicalAddress: false,
      authorisedDeclaration: false,
      truthDeclaration: false,
      dpdpConsent: false,
    },
    agreement: emptyAgreement(),
  };
}

export function emptyAgreement(): MerchantAgreement {
  return {
    read: false,
    authorised: false,
    eSigned: false,
    signerName: '',
    adminSigned: false,
    adminSignerName: '',
  };
}

export function isLive(app: KycApplication | null | undefined): boolean {
  return (
    app?.status === 'activated' &&
    !!app.agreement?.eSigned &&
    !!app.agreement?.adminSigned
  );
}

export function kycDone(app: KycApplication | null | undefined): boolean {
  return !!app?.signatory.verified;
}

export function kybApproved(app: KycApplication | null | undefined): boolean {
  return (
    app?.status === 'pending_agreement' ||
    app?.status === 'pending_admin_sign' ||
    app?.status === 'activated'
  );
}

export function agreementDone(app: KycApplication | null | undefined): boolean {
  return !!app?.agreement?.eSigned && !!app?.agreement?.adminSigned;
}

export function partnerSigned(app: KycApplication | null | undefined): boolean {
  return !!app?.agreement?.eSigned;
}

export const PARTNER_TYPE_LABELS: Record<Exclude<PartnerType, 'admin'>, string> = {
  corporate: 'Corporate',
  staff: 'Payswap staff',
};

export const LEAD_STATUSES: LeadStatus[] = [
  'new',
  'contacted',
  'qualified',
  'kyc',
  'commercial',
  'won',
  'lost',
];

export const LEAD_STATUS_LABELS: Record<LeadStatus, string> = {
  new: 'New',
  contacted: 'Contacted',
  qualified: 'Qualified',
  kyc: 'KYC',
  commercial: 'Commercial',
  won: 'Won',
  lost: 'Lost',
};

export function panEntityHint(pan: string): EntityType | null {
  const fourth = pan.charAt(3)?.toUpperCase();
  switch (fourth) {
    case 'P':
      return 'individual';
    case 'C':
      return 'private_limited';
    case 'F':
      return 'partnership';
    case 'L':
      return 'llp';
    case 'T':
      return 'trust_society_ngo';
    case 'H':
      return 'huf';
    default:
      return null;
  }
}
