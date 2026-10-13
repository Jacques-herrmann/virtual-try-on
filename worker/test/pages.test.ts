import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getLicenseByCustomer, upsertLicense } from "../src/licenses";
import { call, jsonResponse, mockFetch, now, resetDb, subscription, type Recorded } from "./helpers";

beforeEach(resetDb);
afterEach(() => {
  vi.restoreAllMocks();
});

const resendOk = (r: Recorded) =>
  r.url === "https://api.resend.com/emails" ? jsonResponse({ id: "em_1" }) : undefined;

function stripeCheckout(session: object | null) {
  return (r: Recorded) => {
    if (r.url.startsWith("https://api.stripe.com/v1/checkout/sessions/")) {
      return session ? jsonResponse(session) : jsonResponse({ error: {} }, 404);
    }
    if (r.url.startsWith("https://api.stripe.com/v1/subscriptions/")) {
      return jsonResponse(subscription());
    }
    return undefined;
  };
}

const session = {
  id: "cs_test_1",
  status: "complete",
  customer: "cus_1",
  subscription: "sub_1",
  customer_details: { email: "marie@example.com" },
};

describe("GET /", () => {
  it("offers the trial and the key recovery", async () => {
    const res = await call("/");
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/html");
    const html = await res.text();
    expect(html).toContain('href="https://buy.stripe.test/essai"');
    expect(html).toContain("Essayer 7 jours");
    expect(html).toContain('href="/retrouver"');
    expect(html).toContain("Retrouver ma clé");
    expect(html).toContain('name="viewport"');
  });
});

describe("GET /merci", () => {
  it("shows the key created by the webhook", async () => {
    const lic = await upsertLicense(env.DB, {
      customer: "cus_1",
      email: "marie@example.com",
      subscription: "sub_1",
      status: "trialing",
      periodEnd: now() + 7 * 86400,
      now: now(),
    });
    mockFetch(stripeCheckout(session));
    const res = await call("/merci?session_id=cs_test_1");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain(lic.key);
    expect(html).toContain(`/telecharger?cle=${lic.key}`);
  });

  it("creates the license when the webhook has not arrived yet", async () => {
    const { calls } = mockFetch(stripeCheckout(session));
    const res = await call("/merci?session_id=cs_test_1");
    expect(res.status).toBe(200);
    const lic = await getLicenseByCustomer(env.DB, "cus_1");
    expect(lic).toMatchObject({ email: "marie@example.com", status: "trialing" });
    expect(await res.text()).toContain(lic!.key);
    expect(calls[0]!.url).toBe("https://api.stripe.com/v1/checkout/sessions/cs_test_1");
  });

  it("shows an error page for an unknown session", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockFetch(stripeCheckout(null));
    const res = await call("/merci?session_id=cs_test_nope");
    expect(res.status).toBe(404);
    expect(await res.text()).toContain("Retrouver ma clé");
  });

  it("shows an error page for an unfinished session", async () => {
    mockFetch(stripeCheckout({ ...session, status: "open" }));
    const res = await call("/merci?session_id=cs_test_1");
    expect(res.status).toBe(404);
    expect(await getLicenseByCustomer(env.DB, "cus_1")).toBeNull();
  });

  it.each(["", "?session_id=", "?session_id=../../v1/customers"])(
    "refuses a malformed session id (%s)",
    async (q) => {
      const { calls } = mockFetch();
      expect((await call(`/merci${q}`)).status).toBe(404);
      expect(calls).toHaveLength(0);
    },
  );
});

describe("/retrouver", () => {
  const post = (email: string, ip = "203.0.113.7") =>
    call("/retrouver", {
      method: "POST",
      body: new URLSearchParams({ email }).toString(),
      headers: { "content-type": "application/x-www-form-urlencoded", "cf-connecting-ip": ip },
    });

  beforeEach(async () => {
    await upsertLicense(env.DB, {
      customer: "cus_1",
      email: "marie@example.com",
      subscription: "sub_1",
      status: "active",
      periodEnd: now() + 86400,
      now: now(),
    });
  });

  it("shows the form", async () => {
    const res = await call("/retrouver");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain('method="post"');
    expect(html).toContain('type="email"');
  });

  it("emails the key of a known address", async () => {
    const { calls } = mockFetch(resendOk);
    const res = await post("  Marie@Example.com ");
    expect(res.status).toBe(200);
    expect(calls).toHaveLength(1);
    const lic = await getLicenseByCustomer(env.DB, "cus_1");
    const body = JSON.parse(calls[0]!.body);
    expect(body.to).toEqual(["marie@example.com"]);
    expect(body.text).toContain(lic!.key);
  });

  it("answers the same page for an unknown address, without email", async () => {
    const { calls } = mockFetch(resendOk);
    const known = await (await post("marie@example.com")).text();
    const unknown = await (await post("inconnu@example.com")).text();
    expect(unknown).toBe(known);
    expect(calls).toHaveLength(1);
  });

  it("sends at most 3 emails per hour for an address", async () => {
    const { calls } = mockFetch(resendOk);
    for (let i = 0; i < 4; i++) {
      expect((await post("marie@example.com", `198.51.100.${i}`)).status).toBe(200);
    }
    expect(calls).toHaveLength(3);
  });

  it("allows new requests after an hour", async () => {
    const { calls } = mockFetch(resendOk);
    for (let i = 0; i < 3; i++) await post("marie@example.com");
    await env.DB.prepare("UPDATE recover_requests SET at = at - 3601").run();
    await post("marie@example.com");
    expect(calls).toHaveLength(4);
  });

  it("asks again for an invalid address", async () => {
    const { calls } = mockFetch(resendOk);
    const res = await post("pas-un-email");
    expect(res.status).toBe(400);
    expect(await res.text()).toContain("adresse e-mail");
    expect(calls).toHaveLength(0);
  });
});

describe("GET /aide", () => {
  it("renders the installation help", async () => {
    const res = await call("/aide");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("<h1>Installer Virtual Try-On</h1>");
    expect(html).toContain("<strong>Exécuter quand même</strong>");
    expect(html).toContain("<ol>");
    expect(html).toContain("Clé de licence");
  });
});
