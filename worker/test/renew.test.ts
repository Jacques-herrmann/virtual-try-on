import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { upsertLicense, type License } from "../src/licenses";
import { call, jsonResponse, mockFetch, now, resetDb, type Recorded } from "./helpers";

beforeEach(resetDb);
afterEach(() => {
  vi.restoreAllMocks();
});

function seed(status: string): Promise<License> {
  return upsertLicense(env.DB, {
    customer: "cus_1",
    email: "marie@example.com",
    subscription: "sub_1",
    status,
    periodEnd: now() - 86400,
    now: now(),
  });
}

const post = (key: string) =>
  call("/renouveler", {
    method: "POST",
    body: new URLSearchParams({ cle: key }).toString(),
    headers: { "content-type": "application/x-www-form-urlencoded" },
  });

const checkoutOk = (r: Recorded) =>
  r.url === "https://api.stripe.com/v1/checkout/sessions"
    ? jsonResponse({ id: "cs_test_2", url: "https://checkout.stripe.test/c/cs_test_2" })
    : undefined;

describe("GET /renouveler", () => {
  it("offers to resume an ended subscription", async () => {
    const lic = await seed("canceled");
    const { calls } = mockFetch();
    const res = await call(`/renouveler?cle=${lic.key}`);
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain('action="/renouveler"');
    expect(html).toContain(`value="${lic.key}"`);
    expect(html).toContain("Reprendre mon abonnement");
    expect(calls).toHaveLength(0);
  });

  it("says so when the subscription still runs", async () => {
    const lic = await seed("active");
    mockFetch();
    const res = await call(`/renouveler?cle=${lic.key}`);
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("déjà actif");
    expect(html).not.toContain('action="/renouveler"');
  });

  it.each(["", "?cle=", "?cle=KAL-AAAA-AAAA-AAAA-AAAA"])("refuses an unknown key (%s)", async (q) => {
    mockFetch();
    const res = await call(`/renouveler${q}`);
    expect(res.status).toBe(404);
    expect(await res.text()).toContain("Retrouver ma clé");
  });
});

describe("POST /renouveler", () => {
  it("opens a Stripe payment for the same customer, without a new trial", async () => {
    const lic = await seed("canceled");
    const { calls } = mockFetch(checkoutOk);
    const res = await post(lic.key);
    expect(res.status).toBe(303);
    expect(res.headers.get("location")).toBe("https://checkout.stripe.test/c/cs_test_2");

    const stripe = calls.find((c) => c.url.includes("api.stripe.com"))!;
    expect(stripe.method).toBe("POST");
    expect(stripe.headers.get("authorization")).toBe("Bearer sk_test_fake");
    const form = new URLSearchParams(stripe.body);
    expect(form.get("mode")).toBe("subscription");
    expect(form.get("customer")).toBe("cus_1");
    // Premier prix de STRIPE_PRICE_IDS : le tarif actuel.
    expect(form.get("line_items[0][price]")).toBe("price_vto");
    expect(form.get("line_items[0][quantity]")).toBe("1");
    expect(form.get("success_url")).toBe(
      "https://licence.test/merci?session_id={CHECKOUT_SESSION_ID}",
    );
    expect(form.get("cancel_url")).toBe(`https://licence.test/renouveler?cle=${lic.key}`);
    expect(form.get("allow_promotion_codes")).toBe("true");
    expect(form.has("subscription_data[trial_period_days]")).toBe(false);
  });

  it("does not charge a running subscription twice", async () => {
    const lic = await seed("past_due");
    const { calls } = mockFetch();
    const res = await post(lic.key);
    expect(res.status).toBe(200);
    expect(await res.text()).toContain("déjà actif");
    expect(calls).toHaveLength(0);
  });

  it("refuses an unknown key", async () => {
    const { calls } = mockFetch();
    expect((await post("KAL-AAAA-AAAA-AAAA-AAAA")).status).toBe(404);
    expect(calls).toHaveLength(0);
  });

  it("shows an error page when Stripe refuses", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const lic = await seed("canceled");
    mockFetch((r) => (r.url.includes("api.stripe.com") ? jsonResponse({ error: {} }, 400) : undefined));
    const res = await post(lic.key);
    expect(res.status).toBe(502);
    expect(await res.text()).toContain("Réessaie");
  });
});
