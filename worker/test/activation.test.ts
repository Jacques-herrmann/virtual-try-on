import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { upsertLicense } from "../src/licenses";
import { verifyToken } from "../src/tokens";
import { call, jsonResponse, mockFetch, now, resetDb, subscription, type Recorded } from "./helpers";

const DAY = 86400;
let key: string;

beforeEach(async () => {
  await resetDb();
  mockFetch();
  key = (
    await upsertLicense(env.DB, {
      customer: "cus_1",
      email: "marie@example.com",
      subscription: "sub_1",
      status: "active",
      periodEnd: now() + 30 * DAY,
      now: now(),
    })
  ).key;
});
afterEach(() => {
  vi.restoreAllMocks();
});

function post(path: string, body: unknown) {
  return call(path, {
    method: "POST",
    body: typeof body === "string" ? body : JSON.stringify(body),
    headers: { "content-type": "application/json" },
  });
}

const activate = (deviceId: string, deviceName = `PC ${deviceId}`, k = key) =>
  post("/api/activate", { key: k, device_id: deviceId, device_name: deviceName });

async function devices() {
  const { results } = await env.DB.prepare(
    "SELECT device_id, device_name, last_seen FROM activations WHERE key = ? ORDER BY device_id",
  )
    .bind(key)
    .all<{ device_id: string; device_name: string; last_seen: number }>();
  return results;
}

describe("POST /api/activate", () => {
  it("returns a token for this device", async () => {
    const res = await activate("dev-a", "Bureau");
    expect(res.status).toBe(200);
    const { token } = await res.json<{ token: string }>();
    const claims = await verifyToken(env, token, now());
    expect(claims).toMatchObject({ dev: "dev-a", status: "active" });
    expect(await devices()).toMatchObject([{ device_id: "dev-a", device_name: "Bureau" }]);
  });

  it("accepts the key as typed by the seller", async () => {
    const typed = key.toLowerCase().replaceAll("-", " ");
    expect((await activate("dev-a", "Bureau", typed)).status).toBe(200);
  });

  it("refuses an unknown key", async () => {
    const res = await activate("dev-a", "Bureau", "KAL-0000-0000-0000-0000");
    expect(res.status).toBe(404);
    const body = await res.json<{ code: string; message: string }>();
    expect(body.code).toBe("unknown_key");
    expect(body.message).toContain("n'existe pas");
  });

  it("refuses a malformed key as unknown", async () => {
    const res = await activate("dev-a", "Bureau", "pas une clé");
    expect(res.status).toBe(404);
    expect((await res.json<{ code: string }>()).code).toBe("unknown_key");
  });

  it("refuses an ended subscription", async () => {
    await env.DB.prepare("UPDATE licenses SET status = 'canceled' WHERE key = ?").bind(key).run();
    const res = await activate("dev-a");
    expect(res.status).toBe(403);
    const body = await res.json<{ code: string; message: string }>();
    expect(body.code).toBe("expired");
    expect(body.message).toContain("abonnement est terminé");
    expect(await devices()).toHaveLength(0);
  });

  it("allows two devices and refuses a third with their names", async () => {
    expect((await activate("dev-a", "Bureau")).status).toBe(200);
    expect((await activate("dev-b", "Portable")).status).toBe(200);
    const res = await activate("dev-c", "Salon");
    expect(res.status).toBe(409);
    const body = await res.json<{ code: string; message: string; devices: string[] }>();
    expect(body.code).toBe("too_many_devices");
    expect(body.devices).toEqual(["Bureau", "Portable"]);
    expect(body.message).toContain("2 PC (Bureau, Portable)");
    expect(await devices()).toHaveLength(2);
  });

  it("reactivates the same device without taking a new place", async () => {
    await activate("dev-a", "Bureau");
    await activate("dev-b", "Portable");
    const res = await activate("dev-a", "Bureau renommé");
    expect(res.status).toBe(200);
    expect(await devices()).toMatchObject([
      { device_id: "dev-a", device_name: "Bureau renommé" },
      { device_id: "dev-b" },
    ]);
  });

  it("frees the place of a device unseen for more than 30 days", async () => {
    await activate("dev-a", "Bureau");
    await activate("dev-b", "Portable");
    await env.DB.prepare("UPDATE activations SET last_seen = ? WHERE device_id = 'dev-a'")
      .bind(now() - 31 * DAY)
      .run();
    expect((await activate("dev-c", "Salon")).status).toBe(200);
    expect((await devices()).map((d) => d.device_id)).toEqual(["dev-b", "dev-c"]);
  });

  it("rereads a stale subscription in Stripe before answering", async () => {
    vi.restoreAllMocks();
    const { calls } = mockFetch((r: Recorded) =>
      r.url.includes("api.stripe.com") ? jsonResponse(subscription({ status: "unpaid" })) : undefined,
    );
    await env.DB.prepare("UPDATE licenses SET synced_at = ? WHERE key = ?")
      .bind(now() - 2 * DAY, key)
      .run();
    const res = await activate("dev-a");
    expect(res.status).toBe(403);
    expect(calls).toHaveLength(1);
  });

  it.each([
    ["not json", "{"],
    ["no device", { key: "KAL-0000-0000-0000-0000" }],
    ["no key", { device_id: "dev-a", device_name: "x" }],
    ["wrong types", { key: 1, device_id: 2, device_name: 3 }],
    ["huge device id", { key: "KAL-0000-0000-0000-0000", device_id: "x".repeat(200), device_name: "x" }],
  ])("refuses an invalid body (%s)", async (_name, body) => {
    const res = await post("/api/activate", body);
    expect(res.status).toBe(400);
    expect((await res.json<{ code: string }>()).code).toBe("bad_request");
  });
});

describe("POST /api/token", () => {
  it("refreshes the token and the last seen time", async () => {
    await activate("dev-a");
    await env.DB.prepare("UPDATE activations SET last_seen = 0").run();
    const res = await post("/api/token", { key, device_id: "dev-a" });
    expect(res.status).toBe(200);
    const { token } = await res.json<{ token: string }>();
    expect(await verifyToken(env, token, now())).toMatchObject({ dev: "dev-a" });
    expect((await devices())[0]!.last_seen).toBeGreaterThan(now() - 60);
  });

  it("refuses a device that is not activated", async () => {
    await activate("dev-a");
    const res = await post("/api/token", { key, device_id: "dev-z" });
    expect(res.status).toBe(404);
    expect((await res.json<{ code: string }>()).code).toBe("not_activated");
  });

  it("refuses an unknown key", async () => {
    const res = await post("/api/token", { key: "KAL-0000-0000-0000-0000", device_id: "dev-a" });
    expect((await res.json<{ code: string }>()).code).toBe("unknown_key");
  });

  it("reports an ended subscription", async () => {
    await activate("dev-a");
    await env.DB.prepare("UPDATE licenses SET status = 'unpaid' WHERE key = ?").bind(key).run();
    const res = await post("/api/token", { key, device_id: "dev-a" });
    expect(res.status).toBe(403);
    expect((await res.json<{ code: string }>()).code).toBe("expired");
  });

  it("rereads a stale subscription in Stripe", async () => {
    await activate("dev-a");
    vi.restoreAllMocks();
    const { calls } = mockFetch((r: Recorded) =>
      r.url.includes("api.stripe.com")
        ? jsonResponse(subscription({ status: "past_due" }))
        : undefined,
    );
    await env.DB.prepare("UPDATE licenses SET synced_at = ? WHERE key = ?")
      .bind(now() - 2 * DAY, key)
      .run();
    const res = await post("/api/token", { key, device_id: "dev-a" });
    expect(res.status).toBe(200);
    const { token } = await res.json<{ token: string }>();
    expect((await verifyToken(env, token, now()))!.status).toBe("past_due");
    expect(calls).toHaveLength(1);
  });

  it("refuses an invalid body", async () => {
    expect((await post("/api/token", { key })).status).toBe(400);
  });
});

describe("POST /api/deactivate", () => {
  it("frees the place", async () => {
    await activate("dev-a");
    await activate("dev-b");
    const res = await post("/api/deactivate", { key, device_id: "dev-a" });
    expect(res.status).toBe(200);
    expect((await devices()).map((d) => d.device_id)).toEqual(["dev-b"]);
    expect((await activate("dev-c")).status).toBe(200);
  });

  it("refuses an unknown key", async () => {
    const res = await post("/api/deactivate", { key: "KAL-0000-0000-0000-0000", device_id: "a" });
    expect(res.status).toBe(404);
  });

  it("refuses an invalid body", async () => {
    expect((await post("/api/deactivate", "nope")).status).toBe(400);
  });
});
