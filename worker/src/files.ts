import { EXPIRED_MESSAGE, UNKNOWN_KEY_MESSAGE, lookupLicense } from "./activation";
import type { Env } from "./env";
import { error, notFound, nowSeconds } from "./http";
import { getLicenseByHash, isValidStatus } from "./licenses";
import { errorPage } from "./site/layout";
import { stripeApi } from "./stripe";
import { verifyToken, type TokenClaims } from "./tokens";

/** Durée de cache des petits fichiers relayés (manifeste, données Vinted). */
const CACHE_SECONDS = 300;
const CACHE_ORIGIN = "https://cache.vto-licence.internal";
const VINTED_FILE = /^\/data\/(vinted-v\d{1,3}\.json)$/;

interface Asset {
  id: number;
  name: string;
}

/** Fichiers réservés aux abonnés : `/updates/<nom>` (dernière Release) et `/data/vinted-v<N>.json`. */
export async function handleFile(request: Request, env: Env, path: string): Promise<Response> {
  if (!(await authorize(request, env))) return unauthorized();

  if (path.startsWith("/updates/")) {
    const name = decodeURIComponent(path.slice("/updates/".length));
    if (name === "latest.json") {
      return cached(request, "/updates/latest.json", async () => {
        const res = await releaseAsset(env, name);
        if (res.status !== 200) return res;
        return new Response(res.body, {
          headers: { "content-type": "application/json; charset=utf-8" },
        });
      });
    }
    return releaseAsset(env, name);
  }

  const match = VINTED_FILE.exec(path);
  if (!match) return notFound();
  const file = match[1]!;
  return cached(request, `/data/${file}`, async () => {
    const res = await github(env, `/contents/data/${file}?ref=main`, "application/vnd.github.raw+json");
    if (res.status === 404) return notFound();
    if (!res.ok) return upstreamError("github: fichier illisible", res);
    const headers = new Headers({ "content-type": "application/json; charset=utf-8" });
    const etag = res.headers.get("etag");
    if (etag) headers.set("etag", etag);
    return new Response(res.body, { headers });
  });
}

/** `/telecharger?cle=` : le dernier installeur, pour une clé dont l'abonnement est en cours. */
export async function handleDownload(url: URL, env: Env): Promise<Response> {
  const license = await lookupLicense(env, url.searchParams.get("cle") ?? "", nowSeconds());
  if (!license) return errorPage(404, UNKNOWN_KEY_MESSAGE);
  if (!isValidStatus(license.status)) return errorPage(403, EXPIRED_MESSAGE);

  const release = await latestRelease(env);
  const installer = release?.assets.find((a) => a.name.toLowerCase().endsWith(".exe"));
  if (!installer) {
    return errorPage(502, "Le téléchargement est momentanément indisponible. Réessaie dans quelques minutes.");
  }
  return releaseAsset(env, installer.name, release);
}

/** `/api/portal` : redirige vers le portail client Stripe (carte, factures, résiliation). */
export async function handlePortal(request: Request, env: Env): Promise<Response> {
  const claims = await authorize(request, env);
  if (!claims) return unauthorized();
  const license = await getLicenseByHash(env.DB, claims.lic);
  if (!license?.stripe_customer) return unauthorized();
  try {
    const res = await stripeApi(env, "/billing_portal/sessions", {
      customer: license.stripe_customer,
      return_url: `${env.PUBLIC_BASE_URL}/`,
    });
    if (!res.ok) return upstreamError("stripe: portail refusé", res);
    const { url } = (await res.json()) as { url: string };
    return Response.redirect(url, 302);
  } catch (e) {
    console.error("stripe: portail injoignable", e);
    return unavailable();
  }
}

async function authorize(request: Request, env: Env): Promise<TokenClaims | null> {
  const header = request.headers.get("authorization") ?? "";
  const match = /^Bearer\s+(\S+)$/i.exec(header);
  if (!match) return null;
  const claims = await verifyToken(env, match[1]!, nowSeconds());
  return claims && isValidStatus(claims.status) ? claims : null;
}

async function latestRelease(env: Env): Promise<{ assets: Asset[] } | null> {
  try {
    const res = await github(env, "/releases/latest", "application/vnd.github+json");
    if (!res.ok) {
      console.error("github: dernière Release illisible", res.status);
      return null;
    }
    return (await res.json()) as { assets: Asset[] };
  } catch (e) {
    console.error("github: injoignable", e);
    return null;
  }
}

/** Relaie un fichier de la dernière Release publiée, en flux. */
async function releaseAsset(
  env: Env,
  name: string,
  release?: { assets: Asset[] } | null,
): Promise<Response> {
  release ??= await latestRelease(env);
  if (!release) return unavailable();
  const asset = release.assets.find((a) => a.name === name);
  if (!asset) return notFound();
  try {
    // GitHub redirige vers une URL signée qui refuse l'en-tête Authorization : on suit à la main.
    const redirect = await github(
      env,
      `/releases/assets/${asset.id}`,
      "application/octet-stream",
      "manual",
    );
    const location = redirect.headers.get("location");
    const res =
      redirect.status >= 300 && redirect.status < 400 && location
        ? await fetch(location)
        : redirect;
    if (!res.ok) return upstreamError("github: fichier de Release illisible", res);
    const headers = new Headers({
      "content-type": "application/octet-stream",
      "content-disposition": `attachment; filename="${asset.name}"`,
    });
    const length = res.headers.get("content-length");
    if (length) headers.set("content-length", length);
    return new Response(res.body, { headers });
  } catch (e) {
    console.error("github: injoignable", e);
    return unavailable();
  }
}

function github(
  env: Env,
  path: string,
  accept: string,
  redirect: "follow" | "manual" = "follow",
): Promise<Response> {
  return fetch(`https://api.github.com/repos/${env.GITHUB_REPO}${path}`, {
    headers: {
      authorization: `Bearer ${env.GITHUB_TOKEN}`,
      accept,
      "user-agent": "vto-licence",
      "x-github-api-version": "2022-11-28",
    },
    redirect,
  });
}

const cacheKeys = new Set<string>();

/**
 * Garde 5 min la réponse d'un petit fichier commun à tous les abonnés (la clé de cache ne dépend
 * pas du jeton) et répond 304 si l'app a déjà la même version.
 */
async function cached(
  request: Request,
  path: string,
  load: () => Promise<Response>,
): Promise<Response> {
  const key = CACHE_ORIGIN + path;
  const cache = caches.default;
  let res = await cache.match(key);
  if (!res) {
    try {
      res = await load();
    } catch (e) {
      console.error("relais: source injoignable", path, e);
      return unavailable();
    }
    if (res.status !== 200) return res;
    const body = await res.arrayBuffer();
    const headers = new Headers(res.headers);
    headers.set("cache-control", `max-age=${CACHE_SECONDS}`);
    res = new Response(body, { headers });
    await cache.put(key, res.clone());
    cacheKeys.add(key);
  }
  const headers = new Headers(res.headers);
  headers.set("cache-control", "no-store");
  const etag = headers.get("etag");
  if (etag && request.headers.get("if-none-match") === etag) {
    return new Response(null, { status: 304, headers });
  }
  return new Response(res.body, { headers });
}

/** Vide le cache des fichiers relayés (tests). */
export async function clearFileCache(): Promise<void> {
  for (const key of cacheKeys) await caches.default.delete(key);
  cacheKeys.clear();
}

function unauthorized(): Response {
  return error(401, "unauthorized", "Cette ressource demande un abonnement actif.");
}

function unavailable(): Response {
  return error(502, "unavailable", "Service momentanément indisponible. Réessaie plus tard.");
}

async function upstreamError(what: string, res: Response): Promise<Response> {
  console.error(what, res.status, await res.text().catch(() => ""));
  return unavailable();
}
