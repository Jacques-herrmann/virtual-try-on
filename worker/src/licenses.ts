import { licenseHash } from "./tokens";

/** Alphabet de Crockford : sans I, L, O ni U, pour des clés faciles à recopier. */
export const KEY_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

const VALID_STATUSES = new Set(["trialing", "active", "past_due"]);

export interface License {
  key: string;
  key_hash: string;
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
  // VTO : préfixe des clés émises avant le nom Kaloé, toujours accepté.
  if (raw.length === 19 && /^(KAL|VTO|VT0)/.test(raw)) raw = raw.slice(3);
  if (raw.length !== 16) return null;
  raw = raw.replace(/O/g, "0").replace(/[IL]/g, "1");
  for (const c of raw) if (!KEY_ALPHABET.includes(c)) return null;
  return formatKey(raw);
}

function formatKey(body: string): string {
  return `KAL-${body.match(/.{4}/g)!.join("-")}`;
}

export function isValidStatus(status: string | null | undefined): boolean {
  return status != null && VALID_STATUSES.has(status);
}

export async function getLicense(db: D1Database, key: string): Promise<License | null> {
  const found = await db.prepare("SELECT * FROM licenses WHERE key = ?").bind(key).first<License>();
  if (found || !key.startsWith("KAL-")) return found;
  // Clé émise avant le nom Kaloé (VTO-…) : renommée à sa première utilisation, avec ses PC.
  const legacy = `VTO-${key.slice(4)}`;
  const [renamed] = await db.batch<License>([
    db
      .prepare("UPDATE licenses SET key = ?2, key_hash = ?3 WHERE key = ?1 RETURNING *")
      .bind(legacy, key, await licenseHash(key)),
    db.prepare("UPDATE activations SET key = ?2 WHERE key = ?1").bind(legacy, key),
  ]);
  return renamed!.results[0] ?? null;
}

export async function getLicenseByHash(db: D1Database, hash: string): Promise<License | null> {
  return db.prepare("SELECT * FROM licenses WHERE key_hash = ?").bind(hash).first<License>();
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
  const key = generateKey();
  const lic = await db
    .prepare(
      `INSERT INTO licenses
         (key, key_hash, email, stripe_customer, stripe_subscription, status, period_end,
          synced_at, created_at)
       VALUES (?1, ?8, ?2, ?3, ?4, ?5, ?6, ?7, ?7)
       ON CONFLICT (stripe_customer) DO UPDATE SET
         email = COALESCE(excluded.email, email),
         stripe_subscription = COALESCE(excluded.stripe_subscription, stripe_subscription),
         status = COALESCE(excluded.status, status),
         period_end = COALESCE(excluded.period_end, period_end),
         synced_at = excluded.synced_at
       RETURNING *`,
    )
    .bind(key, u.email, u.customer, u.subscription, u.status, u.periodEnd, u.now, await licenseHash(key))
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

/** Nombre de PC actifs par clé. */
export const MAX_DEVICES = 2;
/** Un PC sans nouvelles depuis 30 jours libère sa place. */
export const DEVICE_IDLE = 30 * 86400;

export interface Activation {
  key: string;
  device_id: string;
  device_name: string;
  last_seen: number;
}

export type ActivationResult = { ok: true } | { ok: false; devices: string[] };

/**
 * Active un PC : met à jour un PC déjà connu, ou prend une place s'il en reste une. Les PC
 * inactifs depuis 30 jours sont d'abord retirés.
 */
export async function activateDevice(
  db: D1Database,
  key: string,
  deviceId: string,
  deviceName: string,
  now: number,
): Promise<ActivationResult> {
  // Une seule requête d'insertion : la limite tient même avec deux activations simultanées.
  const [, , inserted] = await db.batch([
    db.prepare("DELETE FROM activations WHERE key = ? AND last_seen < ?").bind(key, now - DEVICE_IDLE),
    db
      .prepare(
        "UPDATE activations SET device_name = ?3, last_seen = ?4 WHERE key = ?1 AND device_id = ?2",
      )
      .bind(key, deviceId, deviceName, now),
    db
      .prepare(
        `INSERT INTO activations (key, device_id, device_name, last_seen)
         SELECT ?1, ?2, ?3, ?4
         WHERE NOT EXISTS (SELECT 1 FROM activations WHERE key = ?1 AND device_id = ?2)
           AND (SELECT COUNT(*) FROM activations WHERE key = ?1) < ?5`,
      )
      .bind(key, deviceId, deviceName, now, MAX_DEVICES),
  ]);
  if (inserted!.meta.changes > 0) return { ok: true };
  if (await getActivation(db, key, deviceId)) return { ok: true };
  const { results } = await db
    .prepare("SELECT device_name FROM activations WHERE key = ? ORDER BY last_seen, device_id")
    .bind(key)
    .all<{ device_name: string }>();
  return { ok: false, devices: results.map((r) => r.device_name) };
}

export async function getActivation(
  db: D1Database,
  key: string,
  deviceId: string,
): Promise<Activation | null> {
  return db
    .prepare("SELECT * FROM activations WHERE key = ? AND device_id = ?")
    .bind(key, deviceId)
    .first<Activation>();
}

export async function touchActivation(
  db: D1Database,
  key: string,
  deviceId: string,
  now: number,
): Promise<void> {
  await db
    .prepare("UPDATE activations SET last_seen = ? WHERE key = ? AND device_id = ?")
    .bind(now, key, deviceId)
    .run();
}

export async function deactivateDevice(db: D1Database, key: string, deviceId: string): Promise<void> {
  await db.prepare("DELETE FROM activations WHERE key = ? AND device_id = ?").bind(key, deviceId).run();
}
