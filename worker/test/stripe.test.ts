import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getLicense, getLicenseByCustomer, upsertLicense } from "../src/licenses";
import { syncSubscription } from "../src/stripe";
import {
  jsonResponse,
  mockFetch,
  now,
  postWebhook,
  resetDb,
  stripeSignature,
  subscription,
  type Recorded,
} from "./helpers";

beforeEach(resetDb);
afterEach(() => {
  vi.restoreAllMocks();
});

const stripeSub = (sub: object) => (r: Recorded) =>
  r.url.startsWith("https://api.stripe.com/v1/subscriptions/") ? jsonResponse(sub) : undefined;
const resendOk = (r: Recorded) =>
  r.url === "https://api.resend.com/emails" ? jsonResponse({ id: "em_1" }) : undefined;

function checkoutCompleted(id = "evt_1", over: Record<string, unknown> = {}) {
  return {
    id,
    type: "checkout.session.completed",
    data: {
      object: {
        id: "cs_1",
        object: "checkout.session",
        customer: "cus_1",
        subscription: "sub_1",
        customer_details: { email: "marie@example.com" },
        ...over,
      },
    },
  };
}

function subscriptionEvent(type: string, id: string, sub: object) {
  return { id, type, data: { object: sub } };
}

describe("signature", () => {
  it.each([
    ["missing", null],
    ["forged", "t=1,v1=deadbeef"],
    ["garbage", "nonsense"],
  ])("refuses a %s signature", async (_name, sig) => {
    const { calls } = mockFetch();
    const res = await postWebhook(checkoutCompleted(), sig);
    expect(res.status).toBe(400);
    expect(calls).toHaveLength(0);
  });

  it("refuses a signature older than 5 minutes", async () => {
    mockFetch();
    const event = checkoutCompleted();
    const sig = await stripeSignature(JSON.stringify(event), now() - 301);
    expect((await postWebhook(event, sig)).status).toBe(400);
  });

  it("refuses a signature made with another secret", async () => {
    mockFetch();
    const event = checkoutCompleted();
    const sig = await stripeSignature(JSON.stringify(event), now(), "whsec_other");
    expect((await postWebhook(event, sig)).status).toBe(400);
  });
});

describe("checkout.session.completed", () => {
  it("creates the license and emails the key", async () => {
    const { calls } = mockFetch(stripeSub(subscription()), resendOk);
    const res = await postWebhook(checkoutCompleted());
    expect(res.status).toBe(200);

    const lic = await getLicenseByCustomer(env.DB, "cus_1");
    expect(lic).toMatchObject({
      email: "marie@example.com",
      stripe_subscription: "sub_1",
      status: "trialing",
      period_end: 1_900_000_000,
    });

    const stripeCall = calls.find((c) => c.url.includes("api.stripe.com"))!;
    expect(stripeCall.url).toBe("https://api.stripe.com/v1/subscriptions/sub_1");
    expect(stripeCall.headers.get("authorization")).toBe("Bearer sk_test_fake");

    const mail = calls.find((c) => c.url === "https://api.resend.com/emails")!;
    expect(mail.headers.get("authorization")).toBe("Bearer re_fake");
    const body = JSON.parse(mail.body);
    expect(body.to).toEqual(["marie@example.com"]);
    expect(body.text).toContain(lic!.key);
    expect(body.html).toContain(lic!.key);
    expect(body.text).toContain(`https://licence.test/telecharger?cle=${lic!.key}`);
  });

  it("gives the same key back to a returning customer and emails it again", async () => {
    const { calls } = mockFetch(stripeSub(subscription()), resendOk);
    await postWebhook(checkoutCompleted("evt_1"));
    const first = await getLicenseByCustomer(env.DB, "cus_1");
    await postWebhook(checkoutCompleted("evt_2", { subscription: "sub_2" }));
    const second = await getLicenseByCustomer(env.DB, "cus_1");
    expect(second!.key).toBe(first!.key);
    expect(second!.stripe_subscription).toBe("sub_2");
    expect(calls.filter((c) => c.url.includes("resend"))).toHaveLength(2);
  });

  it("ignores an event already received", async () => {
    const { calls } = mockFetch(stripeSub(subscription()), resendOk);
    await postWebhook(checkoutCompleted("evt_1"));
    const res = await postWebhook(checkoutCompleted("evt_1"));
    expect(res.status).toBe(200);
    expect(calls.filter((c) => c.url.includes("resend"))).toHaveLength(1);
  });

  it("keeps the license when the email fails", async () => {
    const err = vi.spyOn(console, "error").mockImplementation(() => {});
    mockFetch(stripeSub(subscription()), (r) =>
      r.url.includes("resend") ? jsonResponse({ message: "down" }, 500) : undefined,
    );
    const res = await postWebhook(checkoutCompleted());
    expect(res.status).toBe(200);
    expect(await getLicenseByCustomer(env.DB, "cus_1")).not.toBeNull();
    expect(err).toHaveBeenCalled();
  });

  it("creates the license even when Stripe cannot be read", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockFetch(
      (r) => (r.url.includes("api.stripe.com") ? jsonResponse({}, 500) : undefined),
      resendOk,
    );
    expect((await postWebhook(checkoutCompleted())).status).toBe(200);
    const lic = await getLicenseByCustomer(env.DB, "cus_1");
    expect(lic).toMatchObject({ stripe_subscription: "sub_1", status: null });
  });
});

describe("customer.subscription.*", () => {
  it.each(["customer.subscription.created", "customer.subscription.updated"])(
    "%s updates status and period end",
    async (type) => {
      mockFetch();
      const res = await postWebhook(
        subscriptionEvent(type, "evt_s", subscription({ status: "active" })),
      );
      expect(res.status).toBe(200);
      expect(await getLicenseByCustomer(env.DB, "cus_1")).toMatchObject({
        status: "active",
        period_end: 1_900_000_000,
        stripe_subscription: "sub_1",
      });
    },
  );

  it("reads current_period_end from the subscription for older API versions", async () => {
    mockFetch();
    const sub = {
      ...subscription({ status: "past_due", current_period_end: 1_950_000_000 }),
      items: { data: [] },
    };
    await postWebhook(subscriptionEvent("customer.subscription.updated", "evt_s", sub));
    expect(await getLicenseByCustomer(env.DB, "cus_1")).toMatchObject({
      status: "past_due",
      period_end: 1_950_000_000,
    });
  });

  it("customer.subscription.deleted expires the license", async () => {
    mockFetch();
    await upsertLicense(env.DB, {
      customer: "cus_1",
      email: "marie@example.com",
      subscription: "sub_1",
      status: "active",
      periodEnd: 1_900_000_000,
      now: now(),
    });
    await postWebhook(
      subscriptionEvent(
        "customer.subscription.deleted",
        "evt_d",
        subscription({ status: "canceled" }),
      ),
    );
    expect((await getLicenseByCustomer(env.DB, "cus_1"))!.status).toBe("canceled");
  });

  it("ignores the end of an old subscription once a new one runs", async () => {
    mockFetch();
    await upsertLicense(env.DB, {
      customer: "cus_1",
      email: null,
      subscription: "sub_2",
      status: "active",
      periodEnd: 1_900_000_000,
      now: now(),
    });
    await postWebhook(
      subscriptionEvent(
        "customer.subscription.deleted",
        "evt_d",
        subscription({ status: "canceled" }),
      ),
    );
    expect(await getLicenseByCustomer(env.DB, "cus_1")).toMatchObject({
      stripe_subscription: "sub_2",
      status: "active",
    });
  });

  it("acknowledges other events without effect", async () => {
    mockFetch();
    const res = await postWebhook({ id: "evt_x", type: "invoice.paid", data: { object: {} } });
    expect(res.status).toBe(200);
  });
});

describe("syncSubscription", () => {
  async function seed(syncedAt: number, status: string | null = "active") {
    return upsertLicense(env.DB, {
      customer: "cus_1",
      email: "marie@example.com",
      subscription: "sub_1",
      status,
      periodEnd: 1_900_000_000,
      now: syncedAt,
    });
  }

  it("rereads Stripe after 24 hours", async () => {
    const t = now();
    const lic = await seed(t - 86401);
    mockFetch(stripeSub(subscription({ status: "unpaid" })));
    const synced = await syncSubscription(env, lic, t);
    expect(synced).toMatchObject({ status: "unpaid", synced_at: t });
    expect((await getLicense(env.DB, lic.key))!.status).toBe("unpaid");
  });

  it("rereads Stripe when the status is still unknown", async () => {
    const t = now();
    const lic = await seed(t - 60, null);
    mockFetch(stripeSub(subscription({ status: "trialing" })));
    expect((await syncSubscription(env, lic, t)).status).toBe("trialing");
  });

  it("trusts D1 within 24 hours", async () => {
    const t = now();
    const lic = await seed(t - 3600);
    const { calls } = mockFetch();
    expect(await syncSubscription(env, lic, t)).toEqual(lic);
    expect(calls).toHaveLength(0);
  });

  it("falls back to D1 when Stripe fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const t = now();
    const lic = await seed(t - 90000);
    mockFetch(() => {
      throw new Error("réseau");
    });
    expect(await syncSubscription(env, lic, t)).toEqual(lic);
  });
});
