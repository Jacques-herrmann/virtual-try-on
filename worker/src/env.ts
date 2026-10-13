export interface Env {
  DB: D1Database;
  PUBLIC_BASE_URL: string;
  GITHUB_REPO: string;
  PAYMENT_LINK_URL: string;
  STRIPE_SECRET_KEY: string;
  STRIPE_WEBHOOK_SECRET: string;
  TOKEN_PRIVATE_KEY: string;
  GITHUB_TOKEN: string;
  RESEND_API_KEY: string;
}
