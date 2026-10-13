declare namespace Cloudflare {
  type WorkerEnv = import("../src/env").Env;
  interface Env extends WorkerEnv {
    TEST_MIGRATIONS: import("cloudflare:test").D1Migration[];
  }
  interface GlobalProps {
    mainModule: typeof import("../src/index");
  }
}
