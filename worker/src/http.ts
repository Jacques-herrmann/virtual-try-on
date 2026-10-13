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

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function nowSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

export function notFound(): Response {
  return error(404, "not_found", "Cette page n'existe pas.");
}
