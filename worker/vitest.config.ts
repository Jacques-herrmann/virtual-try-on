import path from "node:path";
import { cloudflareTest, readD1Migrations } from "@cloudflare/vitest-pool-workers";
import { defineConfig } from "vitest/config";
import tokenFixture from "./test/fixtures/token.json";

export default defineConfig(async () => {
  const migrations = await readD1Migrations(path.join(import.meta.dirname, "migrations"));
  return {
    plugins: [
      cloudflareTest({
        wrangler: { configPath: "./wrangler.toml" },
        miniflare: {
          bindings: {
            TEST_MIGRATIONS: migrations,
            PUBLIC_BASE_URL: "https://licence.test",
            PAYMENT_LINK_URL: "https://buy.stripe.test/essai",
            TOKEN_KEY_ID: tokenFixture.kid,
            TOKEN_PRIVATE_KEY: tokenFixture.private_key_pkcs8,
            STRIPE_SECRET_KEY: "sk_test_fake",
            STRIPE_WEBHOOK_SECRET: "whsec_test_fake",
            GITHUB_TOKEN: "github_pat_fake",
            RESEND_API_KEY: "re_fake",
          },
        },
      }),
    ],
    test: {
      setupFiles: ["./test/setup.ts"],
    },
  };
});
