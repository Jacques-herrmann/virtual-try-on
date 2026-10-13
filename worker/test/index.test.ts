import { exports } from "cloudflare:workers";
import { describe, expect, it } from "vitest";

describe("router", () => {
  it("answers /health", async () => {
    const res = await exports.default.fetch("https://licence.test/health");
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
  });

  it("returns a french json 404 for unknown routes", async () => {
    const res = await exports.default.fetch("https://licence.test/nope");
    expect(res.status).toBe(404);
    const body = await res.json<{ code: string; message: string }>();
    expect(body.code).toBe("not_found");
    expect(body.message).toMatch(/n'existe pas/);
  });
});
