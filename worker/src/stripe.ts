import { sendLicenseEmail } from "./email";
import type { Env } from "./env";
import { error, json, nowSeconds } from "./http";
import {
  getLicenseByCustomer,
  isValidStatus,
  upsertLicense,
  type License,
} from "./licenses";
import { toHex } from "./tokens";

/** Écart toléré entre l'horodatage signé par Stripe et l'horloge du Worker. */
const SIGNATURE_TOLERANCE = 300;
/** Au-delà, le statut d'une licence est relu dans Stripe à l'émission d'un jeton. */
const SYNC_AFTER = 86400;

export interface StripeSubscription {
  id: string;
  customer: string | { id: string };
  status: string;
  current_period_end?: number;
  items?: { data?: { current_period_end?: number; price?: { id: string } }[] };
}

/** Abonnement illisible dans Stripe : impossible de savoir s'il concerne Virtual Try-On. */
export class StripeUnavailable extends Error {}

export interface StripeCheckoutSession {
  id: string;
  customer: string | { id: string } | null;
  subscription: string | { id: string } | null;
  customer_details?: { email?: string | null } | null;
  customer_email?: string | null;
}

interface StripeEvent {
  id: string;
  type: string;
  data: { object: unknown };
}

export async function handleWebhook(request: Request, env: Env): Promise<Response> {
  const payload = await request.text();
  const now = nowSeconds();
  const ok = await verifySignature(
    payload,
    request.headers.get("stripe-signature"),
    env.STRIPE_WEBHOOK_SECRET,
    now,
  );
  if (!ok) return error(400, "bad_signature", "Signature Stripe invalide.");

  const event = JSON.parse(payload) as StripeEvent;
  const seen = await env.DB.prepare("SELECT 1 FROM events WHERE id = ?").bind(event.id).first();
  if (seen) return json({ received: true });

  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object as StripeCheckoutSession;
      let license: License | null;
      try {
        license = await licenseFromSession(env, session, now);
      } catch (e) {
        if (!(e instanceof StripeUnavailable)) throw e;
        // Événement non noté : Stripe le renverra.
        return error(500, "stripe_unavailable", "Stripe injoignable, réessayer plus tard.");
      }
      if (license?.email) await sendLicenseEmail(env, license.email, license.key);
      break;
    }
    case "customer.subscription.created":
    case "customer.subscription.updated":
    case "customer.subscription.deleted":
      await applySubscription(env, event.data.object as StripeSubscription, now);
      break;
  }

  // Noté après traitement : un échec (500) laisse Stripe renvoyer l'événement.
  await env.DB.prepare("INSERT OR IGNORE INTO events (id, received_at) VALUES (?, ?)")
    .bind(event.id, now)
    .run();
  return json({ received: true });
}

/**
 * Crée ou reprend la licence d'une session de paiement terminée (webhook ou page /merci).
 * `null` si la session n'est pas un abonnement à Virtual Try-On (le compte Stripe peut
 * vendre autre chose) ; `StripeUnavailable` si l'abonnement ne peut pas être lu.
 */
export async function licenseFromSession(
  env: Env,
  session: StripeCheckoutSession,
  now: number,
): Promise<License | null> {
  const customer = idOf(session.customer);
  const subId = idOf(session.subscription);
  if (!customer || !subId) return null;
  const sub = await fetchSubscription(env, subId);
  if (!sub) throw new StripeUnavailable(subId);
  if (!isOurs(env, sub)) return null;
  return upsertLicense(env.DB, {
    customer,
    email: session.customer_details?.email ?? session.customer_email ?? null,
    subscription: subId,
    status: sub.status,
    periodEnd: periodEnd(sub),
    now,
  });
}

async function applySubscription(env: Env, sub: StripeSubscription, now: number): Promise<void> {
  if (!isOurs(env, sub)) return;
  const customer = idOf(sub.customer)!;
  const current = await getLicenseByCustomer(env.DB, customer);
  // Fin tardive d'un ancien abonnement alors qu'un nouveau a pris le relais : rien à faire.
  if (
    current?.stripe_subscription &&
    current.stripe_subscription !== sub.id &&
    !isValidStatus(sub.status)
  ) {
    return;
  }
  await upsertLicense(env.DB, {
    customer,
    email: null,
    subscription: sub.id,
    status: sub.status,
    periodEnd: periodEnd(sub),
    now,
  });
}

/**
 * Relit l'abonnement dans Stripe si la licence n'a pas été recalée depuis 24 h (webhook perdu).
 * Stripe injoignable : la licence de D1 fait foi.
 */
export async function syncSubscription(env: Env, license: License, now: number): Promise<License> {
  if (!license.stripe_subscription) return license;
  const stale = license.status == null || now - (license.synced_at ?? 0) > SYNC_AFTER;
  if (!stale) return license;
  const sub = await fetchSubscription(env, license.stripe_subscription);
  if (!sub) return license;
  const updated = await env.DB.prepare(
    `UPDATE licenses SET status = ?2, period_end = COALESCE(?3, period_end), synced_at = ?4
     WHERE key = ?1 RETURNING *`,
  )
    .bind(license.key, sub.status, periodEnd(sub), now)
    .first<License>();
  return updated ?? license;
}

export async function stripeApi(
  env: Env,
  path: string,
  form?: Record<string, string>,
): Promise<Response> {
  return fetch(`https://api.stripe.com/v1${path}`, {
    method: form ? "POST" : "GET",
    headers: {
      authorization: `Bearer ${env.STRIPE_SECRET_KEY}`,
      ...(form ? { "content-type": "application/x-www-form-urlencoded" } : {}),
    },
    body: form ? new URLSearchParams(form).toString() : undefined,
  });
}

async function fetchSubscription(env: Env, id: string): Promise<StripeSubscription | null> {
  try {
    const res = await stripeApi(env, `/subscriptions/${encodeURIComponent(id)}`);
    if (!res.ok) {
      console.error("stripe: abonnement illisible", id, res.status);
      return null;
    }
    return (await res.json()) as StripeSubscription;
  } catch (e) {
    console.error("stripe: injoignable", e);
    return null;
  }
}

/** L'abonnement porte-t-il un des prix de Virtual Try-On (`STRIPE_PRICE_IDS`) ? */
function isOurs(env: Env, sub: StripeSubscription): boolean {
  const prices = new Set(env.STRIPE_PRICE_IDS.split(",").map((p) => p.trim()).filter(Boolean));
  return (sub.items?.data ?? []).some((item) => item.price && prices.has(item.price.id));
}

/** Fin de la période en cours ; portée par les éléments de l'abonnement depuis l'API 2025-03-31. */
function periodEnd(sub: StripeSubscription): number | null {
  return sub.items?.data?.[0]?.current_period_end ?? sub.current_period_end ?? null;
}

function idOf(v: string | { id: string } | null | undefined): string | null {
  if (!v) return null;
  return typeof v === "string" ? v : v.id;
}

/** Vérifie l'en-tête `Stripe-Signature` (`t=…,v1=…`) : HMAC-SHA256 de `t.payload`. */
export async function verifySignature(
  payload: string,
  header: string | null,
  secret: string,
  now: number,
): Promise<boolean> {
  if (!header) return false;
  let t: number | null = null;
  const signatures: string[] = [];
  for (const part of header.split(",")) {
    const [k, v] = part.split("=", 2);
    if (k === "t" && v) t = Number(v);
    else if (k === "v1" && v) signatures.push(v);
  }
  if (t == null || !Number.isFinite(t) || signatures.length === 0) return false;
  if (Math.abs(now - t) > SIGNATURE_TOLERANCE) return false;

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = new Uint8Array(
    await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(`${t}.${payload}`)),
  );
  const expected = toHex(mac);
  return signatures.some((s) => timingSafeEqual(s, expected));
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
