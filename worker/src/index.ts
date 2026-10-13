import { handleActivate, handleDeactivate, handleToken } from "./activation";
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
  if (method === "POST" && url.pathname === "/api/activate") return handleActivate(request, env);
  if (method === "POST" && url.pathname === "/api/token") return handleToken(request, env);
  if (method === "POST" && url.pathname === "/api/deactivate") return handleDeactivate(request, env);

  return notFound();
}
