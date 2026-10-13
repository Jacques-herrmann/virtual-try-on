export function json(body: unknown, status = 200, headers: HeadersInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...headers },
  });
}

/** Erreur destinée à l'app : `code` stable, `message` en français. */
export function error(status: number, code: string, message: string, extra: object = {}): Response {
  return json({ code, message, ...extra }, status);
}

export function notFound(): Response {
  return error(404, "not_found", "Cette page n'existe pas.");
}
