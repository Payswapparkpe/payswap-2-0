export interface MarketConfig {
  locale: string;
  currency: string;
  timezone: string;
  dialingCode: string;
  mobileLabel: string;
}

export const DEFAULT_MARKET: MarketConfig = {
  locale: 'en-IN',
  currency: 'INR',
  timezone: 'Asia/Kolkata',
  dialingCode: '+91',
  mobileLabel: '10-digit Indian mobile',
};

export const SUPPORTED_MARKETS: Record<string, MarketConfig> = {
  in: DEFAULT_MARKET,
  us: {
    locale: 'en-US',
    currency: 'USD',
    timezone: 'America/New_York',
    dialingCode: '+1',
    mobileLabel: '10-digit mobile',
  },
};
