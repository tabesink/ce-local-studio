import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(__dirname, "../../../..");

export function loadStackEnv(): Record<string, string> {
  const values: Record<string, string> = {};
  const envPath = path.join(ROOT, ".env.stack.local");
  if (fs.existsSync(envPath)) {
    for (const line of fs.readFileSync(envPath, "utf8").split("\n")) {
      const stripped = line.trim();
      if (!stripped || stripped.startsWith("#") || !stripped.includes("=")) continue;
      const eq = stripped.indexOf("=");
      const key = stripped.slice(0, eq).trim();
      let value = stripped.slice(eq + 1).trim();
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      values[key] = value;
    }
  }
  for (const [key, value] of Object.entries(process.env)) {
    if (value !== undefined && value !== "") values[key] = value;
  }
  return values;
}

export function requireAdminCredentials(env: Record<string, string>): {
  username: string;
  password: string;
} {
  const username = env.CE_ADMIN_USERNAME;
  const password = env.CE_ADMIN_PASSWORD;
  if (!username || !password) {
    throw new Error(
      "CE_ADMIN_USERNAME and CE_ADMIN_PASSWORD must be set (e.g. in .env.stack.local).",
    );
  }
  return { username, password };
}
