/** Alphabet de Crockford : sans I, L, O ni U, pour des clés faciles à recopier. */
export const KEY_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

const VALID_STATUSES = new Set(["trialing", "active", "past_due"]);

export interface License {
  key: string;
  email: string | null;
  stripe_customer: string | null;
  stripe_subscription: string | null;
  status: string | null;
  period_end: number | null;
  synced_at: number | null;
  created_at: number;
}

export function generateKey(): string {
  // 256 est un multiple de 32 : `octet & 31` reste uniforme.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return formatKey(Array.from(bytes, (b) => KEY_ALPHABET[b & 31]).join(""));
}

/** Rend la forme canonique d'une clé saisie à la main, ou `null` si elle est mal formée. */
export function normalizeKey(input: string): string | null {
  let raw = input.toUpperCase().replace(/[\s\-_]/g, "");
  if (raw.length === 19 && (raw.startsWith("VTO") || raw.startsWith("VT0"))) raw = raw.slice(3);
  if (raw.length !== 16) return null;
  raw = raw.replace(/O/g, "0").replace(/[IL]/g, "1");
  for (const c of raw) if (!KEY_ALPHABET.includes(c)) return null;
  return formatKey(raw);
}

function formatKey(body: string): string {
  return `VTO-${body.match(/.{4}/g)!.join("-")}`;
}

export function isValidStatus(status: string | null | undefined): boolean {
  return status != null && VALID_STATUSES.has(status);
}

export async function getLicense(db: D1Database, key: string): Promise<License | null> {
  return db.prepare("SELECT * FROM licenses WHERE key = ?").bind(key).first<License>();
}

export async function getLicenseByCustomer(
  db: D1Database,
  customer: string,
): Promise<License | null> {
  return db.prepare("SELECT * FROM licenses WHERE stripe_customer = ?").bind(customer).first<License>();
}

export async function getLicenseByEmail(db: D1Database, email: string): Promise<License | null> {
  return db
    .prepare("SELECT * FROM licenses WHERE lower(email) = lower(?) ORDER BY created_at DESC LIMIT 1")
    .bind(email.trim())
    .first<License>();
}

export interface LicenseUpsert {
  customer: string;
  email: string | null;
  subscription: string | null;
  status: string | null;
  periodEnd: number | null;
  now: number;
}

/**
 * Crée la licence d'un client Stripe, ou met à jour la sienne : un client garde toujours la même
 * clé. Les champs `null` conservent la valeur connue.
 */
export async function upsertLicense(db: D1Database, u: LicenseUpsert): Promise<License> {
  const lic = await db
    .prepare(
      `INSERT INTO licenses
         (key, email, stripe_customer, stripe_subscription, status, period_end, synced_at, created_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?7)
       ON CONFLICT (stripe_customer) DO UPDATE SET
         email = COALESCE(excluded.email, email),
         stripe_subscription = COALESCE(excluded.stripe_subscription, stripe_subscription),
         status = COALESCE(excluded.status, status),
         period_end = COALESCE(excluded.period_end, period_end),
         synced_at = excluded.synced_at
       RETURNING *`,
    )
    .bind(generateKey(), u.email, u.customer, u.subscription, u.status, u.periodEnd, u.now)
    .first<License>();
  return lic!;
}

export interface SubscriptionUpdate {
  status: string;
  periodEnd: number | null;
  now: number;
}

/** Met à jour la licence liée à un abonnement ; `false` si aucune ne l'est. */
export async function updateSubscription(
  db: D1Database,
  subscription: string,
  u: SubscriptionUpdate,
): Promise<boolean> {
  const res = await db
    .prepare(
      `UPDATE licenses SET status = ?2, period_end = COALESCE(?3, period_end), synced_at = ?4
       WHERE stripe_subscription = ?1`,
    )
    .bind(subscription, u.status, u.periodEnd, u.now)
    .run();
  return res.meta.changes > 0;
}
