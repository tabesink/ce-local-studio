import type { FullConfig } from "@playwright/test";
import { request } from "@playwright/test";
import { seedIndexedDomain } from "./helpers/stack-seed";

async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0]?.use?.baseURL ?? "http://127.0.0.1:3000";

  const probe = await request.newContext({ baseURL });
  try {
    const loginPage = await probe.get("/login");
    if (!loginPage.ok()) {
      throw new Error(
        `Playwright global setup: ${baseURL}/login returned HTTP ${loginPage.status()}. ` +
          "Start the stack first: docker compose --env-file .env.stack.local -f compose.stack.yml up --build -d",
      );
    }
  } catch (error) {
    if (error instanceof Error && error.message.includes("Playwright global setup")) {
      throw error;
    }
    throw new Error(
      `Playwright global setup: ${baseURL}/login is unreachable. ` +
        "Start the stack first: docker compose --env-file .env.stack.local -f compose.stack.yml up --build -d",
      { cause: error },
    );
  } finally {
    await probe.dispose();
  }

  await seedIndexedDomain(baseURL);
}

export default globalSetup;
