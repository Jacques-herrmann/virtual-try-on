import { env } from "cloudflare:workers";
import { describe, expect, it } from "vitest";
import fixture from "./fixtures/token.json";
import { TOKEN_MAX_AGE, licenseHash, signToken, verifyToken } from "../src/tokens";

const b64urlDecode = (s: string) =>
  Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));

function decodePayload(token: string) {
  return JSON.parse(new TextDecoder().decode(b64urlDecode(token.split(".")[0]!)));
}

const input = {
  key: fixture.key,
  deviceId: fixture.payload.dev,
  status: fixture.payload.status,
  periodEnd: fixture.payload.period_end,
  now: fixture.payload.iat,
};

describe("signToken", () => {
  it("writes the expected claims", async () => {
    const token = await signToken(env, input);
    expect(decodePayload(token)).toEqual({
      v: 1,
      kid: "test",
      lic: await licenseHash(fixture.key),
      dev: fixture.payload.dev,
      status: "active",
      period_end: 1_800_000_000,
      exp: 1_799_000_000 + TOKEN_MAX_AGE,
      iat: 1_799_000_000,
    });
    expect(await licenseHash(fixture.key)).toMatch(/^[0-9a-f]{16}$/);
  });

  it("expires at the end of the paid period when it comes first", async () => {
    const token = await signToken(env, { ...input, periodEnd: input.now + 3600 });
    expect(decodePayload(token).exp).toBe(input.now + 3600);
  });

  it("expires after 7 days without a period end", async () => {
    const token = await signToken(env, { ...input, periodEnd: null });
    const payload = decodePayload(token);
    expect(payload.exp).toBe(input.now + 7 * 86400);
    expect(payload.period_end).toBeNull();
  });

  it("matches the shared vector signed by the Python implementation", async () => {
    expect(await signToken(env, input)).toBe(fixture.token);
  });

  it("is verifiable with the published public key", async () => {
    const token = await signToken(env, input);
    const [payload, sig] = token.split(".") as [string, string];
    const pub = await crypto.subtle.importKey(
      "raw",
      Uint8Array.from(atob(fixture.public_key), (c) => c.charCodeAt(0)),
      { name: "Ed25519" },
      false,
      ["verify"],
    );
    const ok = await crypto.subtle.verify(
      "Ed25519",
      pub,
      b64urlDecode(sig),
      new TextEncoder().encode(payload),
    );
    expect(ok).toBe(true);
  });
});

describe("verifyToken", () => {
  it("accepts a valid token", async () => {
    const claims = await verifyToken(env, fixture.token, input.now + 10);
    expect(claims).toMatchObject({ dev: fixture.payload.dev, status: "active" });
  });

  it("refuses a forged signature", async () => {
    const [payload, sig] = fixture.token.split(".") as [string, string];
    const flipped = (sig[0] === "A" ? "B" : "A") + sig.slice(1);
    expect(await verifyToken(env, `${payload}.${flipped}`, input.now)).toBeNull();
  });

  it("refuses a modified payload", async () => {
    const sig = fixture.token.split(".")[1];
    const claims = { ...fixture.payload, status: "active", exp: 2_000_000_000 };
    const payload = btoa(JSON.stringify(claims)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    expect(await verifyToken(env, `${payload}.${sig}`, input.now)).toBeNull();
  });

  it("refuses an unknown kid", async () => {
    const other = { ...env, TOKEN_KEY_ID: "k9" };
    expect(await verifyToken(other, fixture.token, input.now)).toBeNull();
  });

  it("refuses an expired token", async () => {
    expect(await verifyToken(env, fixture.token, fixture.payload.exp)).toBeNull();
    expect(await verifyToken(env, fixture.token, fixture.payload.exp - 1)).not.toBeNull();
  });

  it.each(["", "abc", "a.b.c", "!!!.???"])("refuses garbage %j", async (t) => {
    expect(await verifyToken(env, t, input.now)).toBeNull();
  });
});
