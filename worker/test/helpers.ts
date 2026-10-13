import { createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { env } from "cloudflare:workers";
import { vi } from "vitest";
import worker from "../src/index";

export const BASE = "https://licence.test";

/** Appelle le Worker directement : les `fetch` sortants passent par l'espion de `mockFetch`. */
export async function call(path: string, init?: RequestInit): Promise<Response> {
  const ctx = createExecutionContext();
  const res = await worker.fetch(new Request(BASE + path, init), env, ctx);
  await waitOnExecutionContext(ctx);
  return res;
}

export interface Recorded {
  url: string;
  method: string;
  headers: Headers;
  body: string;
}

export type Route = (req: Recorded) => Response | Promise<Response> | undefined;

/** Remplace `fetch` : chaque appel sortant est enregistré, et un appel sans réponse échoue. */
export function mockFetch(...routes: Route[]) {
  const calls: Recorded[] = [];
  const spy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const req = new Request(input, init);
    const rec: Recorded = {
      url: req.url,
      method: req.method,
      headers: req.headers,
      body: req.body ? await req.text() : "",
    };
    calls.push(rec);
    for (const r of routes) {
      const res = await r(rec);
      if (res) return res;
    }
    throw new Error(`fetch inattendu : ${rec.method} ${rec.url}`);
  });
  return { calls, spy };
}

export const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

export function now(): number {
  return Math.floor(Date.now() / 1000);
}

async function hmacHex(secret: string, data: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(data)));
  return Array.from(sig, (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function stripeSignature(
  payload: string,
  t = now(),
  secret = env.STRIPE_WEBHOOK_SECRET,
): Promise<string> {
  return `t=${t},v1=${await hmacHex(secret, `${t}.${payload}`)}`;
}

export async function postWebhook(event: object, signature?: string | null): Promise<Response> {
  const payload = JSON.stringify(event);
  const headers: Record<string, string> = { "content-type": "application/json" };
  const sig = signature === undefined ? await stripeSignature(payload) : signature;
  if (sig !== null) headers["stripe-signature"] = sig;
  return call("/stripe/webhook", { method: "POST", body: payload, headers });
}

export function subscription(over: Record<string, unknown> = {}) {
  return {
    id: "sub_1",
    object: "subscription",
    customer: "cus_1",
    status: "trialing",
    items: { data: [{ current_period_end: 1_900_000_000 }] },
    ...over,
  };
}

export async function resetDb(): Promise<void> {
  await env.DB.exec(
    "DELETE FROM licenses; DELETE FROM activations; DELETE FROM events; DELETE FROM recover_requests;",
  );
}
