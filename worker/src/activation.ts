import type { Env } from "./env";
import { error, json, nowSeconds } from "./http";
import {
  MAX_DEVICES,
  activateDevice,
  deactivateDevice,
  getActivation,
  getLicense,
  isValidStatus,
  normalizeKey,
  touchActivation,
  type License,
} from "./licenses";
import { syncSubscription } from "./stripe";
import { signToken } from "./tokens";

const MAX_FIELD = 100;

interface DeviceRequest {
  key: string;
  device_id: string;
  device_name: string;
}

export async function handleActivate(request: Request, env: Env): Promise<Response> {
  const body = await readBody(request, true);
  if (!body) return badRequest();
  const now = nowSeconds();
  const found = await findLicense(env, body.key, now);
  if (found instanceof Response) return found;
  if (!isValidStatus(found.status)) return expired();

  const result = await activateDevice(env.DB, found.key, body.device_id, body.device_name, now);
  if (!result.ok) {
    return error(
      409,
      "too_many_devices",
      `Ta clé est déjà utilisée sur ${MAX_DEVICES} PC (${result.devices.join(", ")}). ` +
        "Désactive-la sur l'un d'eux, ou attends 30 jours sans utilisation.",
      { devices: result.devices },
    );
  }
  return tokenResponse(env, found, body.device_id, now);
}

export async function handleToken(request: Request, env: Env): Promise<Response> {
  const body = await readBody(request, false);
  if (!body) return badRequest();
  const now = nowSeconds();
  const found = await findLicense(env, body.key, now);
  if (found instanceof Response) return found;
  if (!(await getActivation(env.DB, found.key, body.device_id))) {
    return error(404, "not_activated", "Ce PC n'est pas activé avec cette clé.");
  }
  await touchActivation(env.DB, found.key, body.device_id, now);
  if (!isValidStatus(found.status)) return expired();
  return tokenResponse(env, found, body.device_id, now);
}

export async function handleDeactivate(request: Request, env: Env): Promise<Response> {
  const body = await readBody(request, false);
  if (!body) return badRequest();
  const key = normalizeKey(body.key);
  const license = key ? await getLicense(env.DB, key) : null;
  if (!license) return unknownKey();
  await deactivateDevice(env.DB, license.key, body.device_id);
  return json({ ok: true });
}

async function findLicense(env: Env, rawKey: string, now: number): Promise<License | Response> {
  return (await lookupLicense(env, rawKey, now)) ?? unknownKey();
}

/** Licence d'une clé saisie, recalée sur Stripe si besoin ; `null` si la clé n'existe pas. */
export async function lookupLicense(env: Env, rawKey: string, now: number): Promise<License | null> {
  const key = normalizeKey(rawKey);
  const license = key ? await getLicense(env.DB, key) : null;
  return license && syncSubscription(env, license, now);
}

async function tokenResponse(
  env: Env,
  license: License,
  deviceId: string,
  now: number,
): Promise<Response> {
  const token = await signToken(env, {
    key: license.key,
    deviceId,
    status: license.status!,
    periodEnd: license.period_end,
    now,
  });
  return json({ token });
}

async function readBody(request: Request, withName: boolean): Promise<DeviceRequest | null> {
  let raw: unknown;
  try {
    raw = await request.json();
  } catch {
    return null;
  }
  if (typeof raw !== "object" || raw === null) return null;
  const { key, device_id, device_name } = raw as Record<string, unknown>;
  if (!isField(key) || !isField(device_id)) return null;
  if (withName && !isField(device_name)) return null;
  const name = typeof device_name === "string" ? device_name.trim() : "";
  return { key, device_id, device_name: name || "PC" };
}

function isField(v: unknown): v is string {
  return typeof v === "string" && v.trim().length > 0 && v.length <= MAX_FIELD;
}

function badRequest(): Response {
  return error(400, "bad_request", "Requête invalide.");
}

export const UNKNOWN_KEY_MESSAGE =
  "Cette clé de licence n'existe pas. Vérifie-la dans l'e-mail reçu après l'achat.";
export const EXPIRED_MESSAGE =
  "Ton abonnement est terminé. Renouvelle-le pour continuer à générer et à envoyer sur Vinted.";

function unknownKey(): Response {
  return error(404, "unknown_key", UNKNOWN_KEY_MESSAGE);
}

function expired(): Response {
  return error(403, "expired", EXPIRED_MESSAGE);
}
