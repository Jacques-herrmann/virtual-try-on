export interface Env {
  DB: D1Database;
  PUBLIC_BASE_URL: string;
  GITHUB_REPO: string;
  PAYMENT_LINK_URL: string;
  /** Prix Stripe de Wearo, séparés par des virgules ; les autres sont ignorés. */
  STRIPE_PRICE_IDS: string;
  TOKEN_KEY_ID: string;
  EMAIL_FROM: string;
  STRIPE_SECRET_KEY: string;
  STRIPE_WEBHOOK_SECRET: string;
  TOKEN_PRIVATE_KEY: string;
  GITHUB_TOKEN: string;
  RESEND_API_KEY: string;
}
