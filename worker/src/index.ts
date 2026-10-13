import type { Env } from "./env";
import { json, notFound } from "./http";
import { handleWebhook } from "./stripe";

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    return route(request, env, ctx);
  },
} satisfies ExportedHandler<Env>;

async function route(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
  const url = new URL(request.url);
  const method = request.method;

  if (method === "GET" && url.pathname === "/health") return json({ ok: true });
  if (method === "POST" && url.pathname === "/stripe/webhook") return handleWebhook(request, env);

  return notFound();
}
