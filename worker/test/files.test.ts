import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearFileCache } from "../src/files";
import { upsertLicense, type License } from "../src/licenses";
import { signToken } from "../src/tokens";
import { call, jsonResponse, mockFetch, now, resetDb, type Recorded } from "./helpers";

const API = "https://api.github.com/repos/Jacques-herrmann/virtual-try-on";
const INSTALLER = "Kaloe-Setup-0.3.0.exe";
const MANIFEST = JSON.stringify({ version: "0.3.0", url: "x", sha256: "0".repeat(64) });

let license: License;

beforeEach(async () => {
  await resetDb();
  await clearFileCache();
  license = await upsertLicense(env.DB, {
    customer: "cus_1",
    email: "marie@example.com",
    subscription: "sub_1",
    status: "active",
    periodEnd: now() + 30 * 86400,
    now: now(),
  });
});
afterEach(() => {
  vi.restoreAllMocks();
});

async function token(over: { now?: number; periodEnd?: number } = {}) {
  return signToken(env, {
    key: license.key,
    deviceId: "dev-a",
    status: "active",
    periodEnd: over.periodEnd ?? now() + 30 * 86400,
    now: over.now ?? now(),
  });
}

const auth = async (t?: string) => ({ authorization: `Bearer ${t ?? (await token())}` });

/** Faux GitHub : dernière Release publiée avec `latest.json` et l'installeur, et `main`. */
function github(opts: { etag?: string } = {}) {
  const etag = opts.etag ?? '"v1-etag"';
  return (r: Recorded) => {
    if (r.url === `${API}/releases/latest`) {
      expect(r.headers.get("authorization")).toBe("Bearer github_pat_fake");
      expect(r.headers.get("user-agent")).toBeTruthy();
      return jsonResponse({
        tag_name: "v0.3.0",
        assets: [
          { id: 11, name: "latest.json" },
          { id: 12, name: INSTALLER },
        ],
      });
    }
    if (r.url === `${API}/releases/assets/11` || r.url === `${API}/releases/assets/12`) {
      expect(r.headers.get("accept")).toBe("application/octet-stream");
      const id = r.url.endsWith("11") ? "11" : "12";
      return new Response(null, {
        status: 302,
        headers: { location: `https://objects.github.test/asset-${id}?sig=abc` },
      });
    }
    if (r.url === "https://objects.github.test/asset-11?sig=abc") {
      expect(r.headers.get("authorization")).toBeNull();
      return new Response(MANIFEST, { headers: { "content-type": "application/octet-stream" } });
    }
    if (r.url === "https://objects.github.test/asset-12?sig=abc") {
      expect(r.headers.get("authorization")).toBeNull();
      return new Response("MZ-installer-bytes", {
        headers: { "content-type": "application/octet-stream", "content-length": "18" },
      });
    }
    if (r.url === `${API}/contents/data/vinted-v1.json?ref=main`) {
      expect(r.headers.get("accept")).toBe("application/vnd.github.raw+json");
      return new Response('{"format":1}', { headers: { etag } });
    }
    if (r.url.startsWith(`${API}/contents/data/`)) return new Response("{}", { status: 404 });
    return undefined;
  };
}

describe("authorization", () => {
  it.each(["/updates/latest.json", `/updates/${INSTALLER}`, "/data/vinted-v1.json"])(
    "%s refuses a request without token",
    async (path) => {
      const { calls } = mockFetch(github());
      const res = await call(path);
      expect(res.status).toBe(401);
      expect((await res.json<{ code: string }>()).code).toBe("unauthorized");
      expect(calls).toHaveLength(0);
    },
  );

  it("refuses a forged token", async () => {
    mockFetch(github());
    const t = await token();
    const forged = t.slice(0, -2) + (t.endsWith("AA") ? "BB" : "AA");
    expect((await call("/updates/latest.json", { headers: await auth(forged) })).status).toBe(401);
  });

  it("refuses an expired token", async () => {
    mockFetch(github());
    const t = await token({ now: now() - 8 * 86400 });
    expect((await call("/updates/latest.json", { headers: await auth(t) })).status).toBe(401);
  });

  it("refuses a token carrying an ended subscription", async () => {
    mockFetch(github());
    const t = await signToken(env, {
      key: license.key,
      deviceId: "dev-a",
      status: "canceled",
      periodEnd: null,
      now: now(),
    });
    expect((await call("/data/vinted-v1.json", { headers: await auth(t) })).status).toBe(401);
  });

  it("refuses a token signed with another key id", async () => {
    mockFetch(github());
    const t = await signToken({ ...env, TOKEN_KEY_ID: "old" }, {
      key: license.key,
      deviceId: "dev-a",
      status: "active",
      periodEnd: null,
      now: now(),
    });
    expect((await call("/data/vinted-v1.json", { headers: await auth(t) })).status).toBe(401);
  });
});

describe("/updates", () => {
  it("serves latest.json of the latest published release", async () => {
    mockFetch(github());
    const res = await call("/updates/latest.json", { headers: await auth() });
    expect(res.status).toBe(200);
    expect(await res.text()).toBe(MANIFEST);
    expect(res.headers.get("content-type")).toContain("application/json");
  });

  it("caches latest.json for 5 minutes", async () => {
    const { calls } = mockFetch(github());
    await call("/updates/latest.json", { headers: await auth() });
    const n = calls.length;
    const again = await call("/updates/latest.json", { headers: await auth() });
    expect(await again.text()).toBe(MANIFEST);
    expect(calls).toHaveLength(n);
  });

  it("streams the installer of the same release", async () => {
    mockFetch(github());
    const res = await call(`/updates/${INSTALLER}`, { headers: await auth() });
    expect(res.status).toBe(200);
    expect(await res.text()).toBe("MZ-installer-bytes");
    expect(res.headers.get("content-length")).toBe("18");
    expect(res.headers.get("content-disposition")).toContain(INSTALLER);
  });

  it("answers 404 for an unknown file", async () => {
    mockFetch(github());
    const res = await call("/updates/autre.exe", { headers: await auth() });
    expect(res.status).toBe(404);
  });

  it("answers 502 when GitHub fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockFetch(() => jsonResponse({ message: "boom" }, 500));
    const res = await call("/updates/latest.json", { headers: await auth() });
    expect(res.status).toBe(502);
  });
});

describe("/data", () => {
  it("serves vinted-v1.json from main with its ETag", async () => {
    mockFetch(github());
    const res = await call("/data/vinted-v1.json", { headers: await auth() });
    expect(res.status).toBe(200);
    expect(await res.text()).toBe('{"format":1}');
    expect(res.headers.get("etag")).toBe('"v1-etag"');
  });

  it("answers 304 when the app already has this version", async () => {
    mockFetch(github());
    const res = await call("/data/vinted-v1.json", {
      headers: { ...(await auth()), "if-none-match": '"v1-etag"' },
    });
    expect(res.status).toBe(304);
    expect(res.headers.get("etag")).toBe('"v1-etag"');
  });

  it("answers 200 when the app has an older version", async () => {
    mockFetch(github());
    const res = await call("/data/vinted-v1.json", {
      headers: { ...(await auth()), "if-none-match": '"old"' },
    });
    expect(res.status).toBe(200);
  });

  it("answers 404 for a format that does not exist", async () => {
    mockFetch(github());
    expect((await call("/data/vinted-v9.json", { headers: await auth() })).status).toBe(404);
  });

  it.each(["/data/autre.json", "/data/vinted-v1.json.bak", "/data/..%2Fsecret"])(
    "refuses other paths (%s)",
    async (path) => {
      const { calls } = mockFetch(github());
      expect((await call(path, { headers: await auth() })).status).toBe(404);
      expect(calls).toHaveLength(0);
    },
  );
});

describe("/telecharger", () => {
  it("streams the installer for a valid key", async () => {
    mockFetch(github());
    const res = await call(`/telecharger?cle=${encodeURIComponent(license.key.toLowerCase())}`);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-disposition")).toContain(INSTALLER);
    expect(await res.text()).toBe("MZ-installer-bytes");
  });

  it("shows an error page for an unknown key", async () => {
    mockFetch(github());
    const res = await call("/telecharger?cle=VTO-0000-0000-0000-0000");
    expect(res.status).toBe(404);
    expect(res.headers.get("content-type")).toContain("text/html");
    expect(await res.text()).toContain("existe pas");
  });

  it("shows an error page for an ended subscription", async () => {
    mockFetch(github());
    await env.DB.prepare("UPDATE licenses SET status = 'canceled'").run();
    const res = await call(`/telecharger?cle=${license.key}`);
    expect(res.status).toBe(403);
    expect(await res.text()).toContain("abonnement est terminé");
  });

  it("shows an error page without key", async () => {
    mockFetch(github());
    expect((await call("/telecharger")).status).toBe(404);
  });
});

describe("/api/portal", () => {
  it("redirects to a Stripe billing portal session", async () => {
    const { calls } = mockFetch((r) =>
      r.url === "https://api.stripe.com/v1/billing_portal/sessions"
        ? jsonResponse({ url: "https://billing.stripe.test/session/abc" })
        : undefined,
    );
    const res = await call("/api/portal", { headers: await auth(), redirect: "manual" });
    expect(res.status).toBe(302);
    expect(res.headers.get("location")).toBe("https://billing.stripe.test/session/abc");
    const form = new URLSearchParams(calls[0]!.body);
    expect(form.get("customer")).toBe("cus_1");
    expect(form.get("return_url")).toBe("https://licence.test/");
  });

  it("refuses a request without token", async () => {
    mockFetch();
    expect((await call("/api/portal")).status).toBe(401);
  });

  it("answers 502 when Stripe fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockFetch(() => jsonResponse({}, 500));
    expect((await call("/api/portal", { headers: await auth() })).status).toBe(502);
  });
});
