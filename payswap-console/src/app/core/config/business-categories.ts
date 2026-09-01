export interface BusinessCategory {
  id: string;
  label: string;
  subCategories: { id: string; label: string }[];
}

export const BUSINESS_CATEGORIES: BusinessCategory[] = [
  {
    id: 'gifting',
    label: 'Corporate gifting & prepaid',
    subCategories: [
      { id: 'brand_vouchers', label: 'Brand vouchers' },
      { id: 'prepaid_cards', label: 'Prepaid / meal cards' },
      { id: 'rewards', label: 'Employee rewards' },
      { id: 'payouts', label: 'Vendor / inclusive payouts' },
    ],
  },
  {
    id: 'saas',
    label: 'SaaS / Software',
    subCategories: [
      { id: 'b2b_saas', label: 'B2B SaaS' },
      { id: 'marketplace_saas', label: 'Marketplace platform' },
      { id: 'supplements_saas', label: 'Health & beauty supplements' },
    ],
  },
  {
    id: 'ecommerce',
    label: 'E-commerce',
    subCategories: [
      { id: 'retail', label: 'Online retail' },
      { id: 'marketplace', label: 'Marketplace seller' },
      { id: 'd2c', label: 'Direct-to-consumer brand' },
    ],
  },
  {
    id: 'education',
    label: 'Education',
    subCategories: [
      { id: 'school', label: 'School / college' },
      { id: 'vocational', label: 'Vocational / coaching' },
      { id: 'edtech', label: 'EdTech' },
    ],
  },
  {
    id: 'healthcare',
    label: 'Healthcare',
    subCategories: [
      { id: 'clinic', label: 'Clinic / hospital' },
      { id: 'pharmacy', label: 'Pharmacy' },
      { id: 'diagnostics', label: 'Diagnostics' },
    ],
  },
  {
    id: 'travel',
    label: 'Travel',
    subCategories: [
      { id: 'agency', label: 'Tours & travel agency' },
      { id: 'ota', label: 'Online travel aggregator' },
      { id: 'hospitality', label: 'Hotels & stays' },
    ],
  },
  {
    id: 'food',
    label: 'Food & beverage',
    subCategories: [
      { id: 'restaurant', label: 'Restaurant / cloud kitchen' },
      { id: 'packaged', label: 'Packaged foods' },
      { id: 'catering', label: 'Catering' },
    ],
  },
  {
    id: 'finance',
    label: 'Financial services',
    subCategories: [
      { id: 'nbfc', label: 'NBFC / lending' },
      { id: 'brokerage', label: 'Stock brokerage' },
      { id: 'forex', label: 'Forex / remittance' },
    ],
  },
  {
    id: 'utilities',
    label: 'Utilities',
    subCategories: [
      { id: 'electric', label: 'Electric / gas / water' },
      { id: 'telecom', label: 'Telecom' },
    ],
  },
  {
    id: 'other',
    label: 'Other',
    subCategories: [{ id: 'other', label: 'Other / not listed' }],
  },
];

export const MONTHLY_VOLUMES = [
  { id: 'lt_1l', label: 'Under ₹1 lakh' },
  { id: '1_10l', label: '₹1 lakh – ₹10 lakh' },
  { id: '10l_1cr', label: '₹10 lakh – ₹1 crore' },
  { id: '1_10cr', label: '₹1 crore – ₹10 crore' },
  { id: 'gt_10cr', label: 'Above ₹10 crore' },
];
