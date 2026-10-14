export interface Env {
  DB: D1Database;
  PUBLIC_BASE_URL: string;
  GITHUB_REPO: string;
  PAYMENT_LINK_URL: string;
  /** Prix affiché sur le site (« 14,90 € »), par mois. */
  PRICE_LABEL: string;
  /** Prix Stripe de Kaloé, séparés par des virgules ; les autres sont ignorés. */
  STRIPE_PRICE_IDS: string;
  TOKEN_KEY_ID: string;
  EMAIL_FROM: string;
  STRIPE_SECRET_KEY: string;
  STRIPE_WEBHOOK_SECRET: string;
  TOKEN_PRIVATE_KEY: string;
  GITHUB_TOKEN: string;
  RESEND_API_KEY: string;
}
