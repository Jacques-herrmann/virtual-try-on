import type { Env } from "./env";

/** Durée de vie maximale d'un jeton : l'app doit le rafraîchir au moins une fois par semaine. */
export const TOKEN_MAX_AGE = 7 * 86400;

export interface TokenClaims {
  v: 1;
  kid: string;
  lic: string;
  dev: string;
  status: string;
  period_end: number | null;
  exp: number;
  iat: number;
}

export interface TokenInput {
  key: string;
  deviceId: string;
  status: string;
  periodEnd: number | null;
  now: number;
}

/** Empreinte de la clé portée par le jeton : la clé elle-même n'y figure jamais. */
export async function licenseHash(key: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(key));
  return toHex(new Uint8Array(digest)).slice(0, 16);
}

/** Jeton `base64url(payload).base64url(signature Ed25519 de la première partie)`. */
export async function signToken(env: Env, t: TokenInput): Promise<string> {
  const claims: TokenClaims = {
    v: 1,
    kid: env.TOKEN_KEY_ID,
    lic: await licenseHash(t.key),
    dev: t.deviceId,
    status: t.status,
    period_end: t.periodEnd,
    exp: Math.min(t.periodEnd ?? Infinity, t.now + TOKEN_MAX_AGE),
    iat: t.now,
  };
  const payload = b64url(new TextEncoder().encode(JSON.stringify(claims)));
  const { privateKey } = await keyPair(env.TOKEN_PRIVATE_KEY);
  const sig = await crypto.subtle.sign("Ed25519", privateKey, new TextEncoder().encode(payload));
  return `${payload}.${b64url(new Uint8Array(sig))}`;
}

/** Rend le contenu d'un jeton émis par ce Worker et non expiré, sinon `null`. */
export async function verifyToken(env: Env, token: string, now: number): Promise<TokenClaims | null> {
  const parts = token.split(".");
  if (parts.length !== 2) return null;
  const [payload, sig] = parts as [string, string];
  try {
    const { publicKey } = await keyPair(env.TOKEN_PRIVATE_KEY);
    const ok = await crypto.subtle.verify(
      "Ed25519",
      publicKey,
      b64urlDecode(sig),
      new TextEncoder().encode(payload),
    );
    if (!ok) return null;
    const claims = JSON.parse(new TextDecoder().decode(b64urlDecode(payload))) as TokenClaims;
    if (claims.v !== 1 || claims.kid !== env.TOKEN_KEY_ID) return null;
    if (typeof claims.exp !== "number" || claims.exp <= now) return null;
    return claims;
  } catch {
    return null;
  }
}

const pairs = new Map<string, Promise<CryptoKeyPair>>();

function keyPair(pkcs8: string): Promise<CryptoKeyPair> {
  let pair = pairs.get(pkcs8);
  if (!pair) {
    pair = importPair(pkcs8);
    pairs.set(pkcs8, pair);
  }
  return pair;
}

async function importPair(pkcs8: string): Promise<CryptoKeyPair> {
  const der = Uint8Array.from(atob(pkcs8), (c) => c.charCodeAt(0));
  const privateKey = (await crypto.subtle.importKey("pkcs8", der, { name: "Ed25519" }, true, [
    "sign",
  ])) as CryptoKey;
  // Le JWK de la clé privée porte aussi la clé publique (`x`).
  const { x } = (await crypto.subtle.exportKey("jwk", privateKey)) as JsonWebKey;
  const publicKey = (await crypto.subtle.importKey(
    "jwk",
    { kty: "OKP", crv: "Ed25519", x },
    { name: "Ed25519" },
    false,
    ["verify"],
  )) as CryptoKey;
  return { privateKey, publicKey };
}

function b64url(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64urlDecode(s: string): Uint8Array {
  return Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
}

export function toHex(bytes: Uint8Array): string {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
