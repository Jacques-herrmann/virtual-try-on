import { env } from "cloudflare:workers";
import { beforeEach, describe, expect, it } from "vitest";
import keyCases from "./fixtures/keys.json";
import {
  KEY_ALPHABET,
  generateKey,
  getLicense,
  getLicenseByCustomer,
  getLicenseByHash,
  isValidStatus,
  normalizeKey,
  updateSubscription,
  upsertLicense,
} from "../src/licenses";
import { licenseHash } from "../src/tokens";

beforeEach(async () => {
  await env.DB.exec("DELETE FROM licenses; DELETE FROM activations;");
});

describe("keys", () => {
  it("generates KAL-XXXX-XXXX-XXXX-XXXX from the Crockford alphabet", () => {
    for (let i = 0; i < 200; i++) {
      const key = generateKey();
      expect(key).toMatch(/^KAL-[0-9A-HJKMNP-TV-Z]{4}(-[0-9A-HJKMNP-TV-Z]{4}){3}$/);
    }
    expect(KEY_ALPHABET).toHaveLength(32);
    expect(KEY_ALPHABET).not.toMatch(/[ILOU]/);
  });

  it("generates distinct keys", () => {
    const keys = new Set(Array.from({ length: 500 }, generateKey));
    expect(keys.size).toBe(500);
  });

  it.each(keyCases.cases)("normalizes $input", ({ input, expected }) => {
    expect(normalizeKey(input)).toBe(expected);
  });

  it("normalizes its own keys to themselves", () => {
    const key = generateKey();
    expect(normalizeKey(key)).toBe(key);
    expect(normalizeKey(key.toLowerCase().replaceAll("-", " "))).toBe(key);
  });
});

describe("isValidStatus", () => {
  it.each(["trialing", "active", "past_due"])("%s is valid", (s) => {
    expect(isValidStatus(s)).toBe(true);
  });
  it.each(["canceled", "unpaid", "incomplete", "incomplete_expired", "paused", null, ""])(
    "%s is not valid",
    (s) => {
      expect(isValidStatus(s)).toBe(false);
    },
  );
});

describe("storage", () => {
  const base = {
    email: "marie@example.com",
    customer: "cus_1",
    subscription: "sub_1",
    status: "trialing",
    periodEnd: 1_800_000_000,
    now: 1_799_000_000,
  };

  it("creates a license", async () => {
    const lic = await upsertLicense(env.DB, base);
    expect(lic.key).toMatch(/^KAL-/);
    expect(lic).toMatchObject({
      email: "marie@example.com",
      stripe_customer: "cus_1",
      stripe_subscription: "sub_1",
      status: "trialing",
      period_end: 1_800_000_000,
      synced_at: 1_799_000_000,
      created_at: 1_799_000_000,
    });
    expect(await getLicense(env.DB, lic.key)).toEqual(lic);
    expect(await getLicenseByCustomer(env.DB, "cus_1")).toEqual(lic);
    expect(lic.key_hash).toBe(await licenseHash(lic.key));
    expect(await getLicenseByHash(env.DB, lic.key_hash)).toEqual(lic);
  });

  it("keeps one license per Stripe customer", async () => {
    const first = await upsertLicense(env.DB, base);
    const second = await upsertLicense(env.DB, {
      ...base,
      subscription: "sub_2",
      status: "active",
      periodEnd: 1_900_000_000,
      now: 1_850_000_000,
    });
    expect(second.key).toBe(first.key);
    expect(second).toMatchObject({
      stripe_subscription: "sub_2",
      status: "active",
      period_end: 1_900_000_000,
      synced_at: 1_850_000_000,
      created_at: 1_799_000_000,
    });
    const count = await env.DB.prepare("SELECT COUNT(*) AS n FROM licenses").first<number>("n");
    expect(count).toBe(1);
  });

  it("keeps known fields when the update leaves them out", async () => {
    const first = await upsertLicense(env.DB, base);
    const again = await upsertLicense(env.DB, {
      customer: "cus_1",
      email: null,
      subscription: null,
      status: null,
      periodEnd: null,
      now: 1_799_500_000,
    });
    expect(again).toMatchObject({
      key: first.key,
      email: "marie@example.com",
      stripe_subscription: "sub_1",
      status: "trialing",
      period_end: 1_800_000_000,
    });
  });

  it("updates status, period end and sync time by subscription", async () => {
    const lic = await upsertLicense(env.DB, base);
    const updated = await updateSubscription(env.DB, "sub_1", {
      status: "canceled",
      periodEnd: 1_800_500_000,
      now: 1_800_100_000,
    });
    expect(updated).toBe(true);
    expect(await getLicense(env.DB, lic.key)).toMatchObject({
      status: "canceled",
      period_end: 1_800_500_000,
      synced_at: 1_800_100_000,
    });
  });

  it("reports an unknown subscription", async () => {
    expect(
      await updateSubscription(env.DB, "sub_x", { status: "active", periodEnd: 1, now: 1 }),
    ).toBe(false);
  });

  it("returns null for an unknown key", async () => {
    expect(await getLicense(env.DB, "KAL-0000-0000-0000-0000")).toBeNull();
  });

  it("renames a key issued before Kaloé (VTO-…) on first use, with its devices", async () => {
    const old = "VTO-ABCD-EFGH-JKMN-PQRS";
    await env.DB.batch([
      env.DB.prepare(
        `INSERT INTO licenses (key, key_hash, email, stripe_customer, status, created_at)
         VALUES (?, ?, 'marie@example.com', 'cus_1', 'active', 1)`,
      ).bind(old, await licenseHash(old)),
      env.DB.prepare(
        "INSERT INTO activations (key, device_id, device_name, last_seen) VALUES (?, 'dev-a', 'Bureau', 1)",
      ).bind(old),
    ]);

    const lic = await getLicense(env.DB, "KAL-ABCD-EFGH-JKMN-PQRS");
    expect(lic).toMatchObject({ key: "KAL-ABCD-EFGH-JKMN-PQRS", stripe_customer: "cus_1" });
    expect(lic!.key_hash).toBe(await licenseHash("KAL-ABCD-EFGH-JKMN-PQRS"));
    expect(await getLicense(env.DB, old)).toBeNull();
    const { results } = await env.DB.prepare("SELECT key FROM activations").all<{ key: string }>();
    expect(results).toEqual([{ key: "KAL-ABCD-EFGH-JKMN-PQRS" }]);
  });
});
