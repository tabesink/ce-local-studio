import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { request, type APIRequestContext } from "@playwright/test";
import { loadStackEnv, requireAdminCredentials } from "./env";

export const E2E_DOMAIN_ID = "e2e";
export const E2E_DOMAIN_DISPLAY_NAME = "E2E Pilot";
export const E2E_PROVIDER_CREDENTIAL = "e2e-playwright-credential";
export const E2E_DOMAIN_QUESTION = "What does startup require?";
export const E2E_DIRECT_QUESTION = "Say hello in one short sentence.";
export const E2E_MEMBER_USERNAME = "e2e-member@example.test";
export const E2E_MEMBER_PASSWORD = "e2e-member-password";
export const E2E_PREVIEW_MARKDOWN_NAME = "e2e-pilot.md";
export const E2E_PREVIEW_PDF_NAME = "e2e-preview.pdf";

const ARTIFACTS_DIR = path.resolve(__dirname, "../artifacts");
const SEED_PATH = path.join(ARTIFACTS_DIR, "seed.json");
const FIXTURE_PATH = path.resolve(__dirname, "../fixtures/seed-source.md");
const PDF_FIXTURE_PATH = path.resolve(__dirname, "../fixtures/seed-preview.pdf");
const ROOT = path.resolve(__dirname, "../../../..");
const POLL_TIMEOUT_MS = 180_000;
const POLL_INTERVAL_MS = 2_000;

/** Minimal valid PDF for browser <object> preview. */
const MINIMAL_PDF = Buffer.from(
  "%PDF-1.4\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n4 0 obj<< /Length 44 >>stream\nBT /F1 24 Tf 40 80 Td (E2E PDF) Tj ET\nendstream\nendobj\n5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\nxref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000068 00000 n \n0000000125 00000 n \n0000000274 00000 n \n0000000373 00000 n \ntrailer<< /Size 6 /Root 1 0 R >>\nstartxref\n456\n%%EOF\n",
  "utf8",
);

export type SeedInfo = {
  domainId: string;
  displayName: string;
  markdownSourceId?: string;
  pdfSourceId?: string;
};

type DomainRow = {
  id: string;
  displayName: string;
  available?: boolean;
  state?: string;
};

type SourceRow = {
  id?: string;
  state?: string;
  indexState?: string;
  displayName?: string;
  /** @deprecated lifted field — prefer displayName */
  originalFilename?: string;
  contentType?: string;
  documentRef?: string;
};

export function readSeedInfo(): SeedInfo {
  if (!fs.existsSync(SEED_PATH)) {
    throw new Error(`Missing seed file at ${SEED_PATH}. Did global setup run?`);
  }
  return JSON.parse(fs.readFileSync(SEED_PATH, "utf8")) as SeedInfo;
}

function writeSeedInfo(info: SeedInfo) {
  fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
  fs.writeFileSync(SEED_PATH, `${JSON.stringify(info, null, 2)}\n`, "utf8");
}

async function sleep(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function readJson(
  response: Awaited<ReturnType<APIRequestContext["fetch"]>>,
): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new Error(`non-JSON body (HTTP ${response.status()})`);
  }
}

async function jsonOrThrow(
  response: Awaited<ReturnType<APIRequestContext["fetch"]>>,
  label: string,
): Promise<unknown> {
  const status = response.status();
  if (status >= 400) {
    throw new Error(`${label} failed: HTTP ${status}`);
  }
  return readJson(response);
}

function isReadySource(source: SourceRow | undefined): boolean {
  return source?.state === "prepared" && source?.indexState === "ready";
}

async function listSources(api: APIRequestContext, domainId: string): Promise<SourceRow[]> {
  const body = (await jsonOrThrow(
    await api.get(`/api/v1/admin/domains/${domainId}/sources`),
    "list sources",
  )) as { sources?: SourceRow[] };
  return body.sources ?? [];
}

async function findReadySource(
  api: APIRequestContext,
  domainId: string,
): Promise<SourceRow | null> {
  return (await listSources(api, domainId)).find((source) => isReadySource(source)) ?? null;
}

async function ensureDomainStarted(api: APIRequestContext, domain: DomainRow | undefined) {
  if (domain?.available) return;

  const started = await api.post(`/api/v1/admin/domains/${E2E_DOMAIN_ID}/start`);
  if (started.ok()) {
    await readJson(started);
    return;
  }
  if (started.status() === 409) {
    const domainsBody = (await jsonOrThrow(
      await api.get("/api/v1/admin/domains"),
      "list domains after start conflict",
    )) as { domains?: DomainRow[] };
    const refreshed = domainsBody.domains?.find((row) => row.id === E2E_DOMAIN_ID);
    if (refreshed?.available) return;
  }
  throw new Error(`domain start failed: HTTP ${started.status()}`);
}

async function waitForSourceReady(api: APIRequestContext, sourceId: string) {
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const get = await api.get(`/api/v1/admin/domains/${E2E_DOMAIN_ID}/sources/${sourceId}`);
    const body = (await jsonOrThrow(get, "source poll")) as { source?: SourceRow };
    if (isReadySource(body.source)) return;
    await sleep(POLL_INTERVAL_MS);
  }
  throw new Error(
    `source not ready within ${POLL_TIMEOUT_MS / 1000}s (prepared + indexState=ready). Is the stack worker healthy?`,
  );
}

function ensurePdfFixture() {
  if (!fs.existsSync(PDF_FIXTURE_PATH)) {
    fs.mkdirSync(path.dirname(PDF_FIXTURE_PATH), { recursive: true });
    fs.writeFileSync(PDF_FIXTURE_PATH, MINIMAL_PDF);
  }
}

async function ensureNamedSource(
  api: APIRequestContext,
  options: {
    filename: string;
    mimeType: string;
    buffer: Buffer;
    waitReady: boolean;
  },
): Promise<string> {
  const { filename, mimeType, buffer, waitReady } = options;
  const existing = (await listSources(api, E2E_DOMAIN_ID)).find(
    (row) => row.displayName === filename || row.originalFilename === filename,
  );
  if (existing?.id) {
    if (waitReady && !isReadySource(existing)) {
      await waitForSourceReady(api, existing.id);
    }
    return existing.id;
  }

  const upload = await api.post(`/api/v1/admin/domains/${E2E_DOMAIN_ID}/sources`, {
    multipart: {
      file: {
        name: filename,
        mimeType,
        buffer,
      },
    },
  });
  const uploaded = (await jsonOrThrow(upload, `source upload ${filename}`)) as {
    source?: SourceRow;
  };
  const sourceId = uploaded.source?.id;
  if (!sourceId) {
    throw new Error(`source upload ${filename}: source id missing`);
  }
  if (waitReady) {
    await waitForSourceReady(api, sourceId);
  }
  return sourceId;
}

/** Create the E2E member inside the API container (no public create-user route). */
export function ensureE2EMemberUser() {
  const env = loadStackEnv();
  const username = env.CE_E2E_MEMBER_USERNAME || E2E_MEMBER_USERNAME;
  const password = env.CE_E2E_MEMBER_PASSWORD || E2E_MEMBER_PASSWORD;
  const script = `
from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory
from context_engine.models import ROLE_MEMBER, User
from context_engine.services.auth import create_user
from sqlalchemy import select

settings = Settings()
engine = create_db_engine(settings)
db = create_session_factory(engine)()
try:
    existing = db.scalar(select(User).where(User.username == ${JSON.stringify(username)}))
    if existing is None:
        create_user(db, ${JSON.stringify(username)}, ${JSON.stringify(password)}, role=ROLE_MEMBER)
        print("created")
    else:
        print("exists")
finally:
    db.close()
    engine.dispose()
`;
  const projectName =
    process.env.COMPOSE_PROJECT_NAME?.trim() || "context_engine_stack";
  try {
    execFileSync(
      "docker",
      [
        "compose",
        "--env-file",
        ".env.stack.local",
        "-f",
        "compose.stack.yml",
        "-p",
        projectName,
        "exec",
        "-T",
        "api",
        "python",
        "-c",
        script,
      ],
      {
        cwd: ROOT,
        stdio: ["ignore", "pipe", "pipe"],
        encoding: "utf8",
      },
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(
      `Failed to ensure E2E member user via docker compose exec api. ${message}`,
    );
  }
  return { username, password };
}

export async function seedIndexedDomain(baseURL: string): Promise<SeedInfo> {
  const env = loadStackEnv();
  const { username, password } = requireAdminCredentials(env);
  ensurePdfFixture();
  ensureE2EMemberUser();

  const api = await request.newContext({
    baseURL,
    extraHTTPHeaders: { Accept: "application/json" },
  });

  try {
    await jsonOrThrow(
      await api.post("/api/v1/auth/login", { data: { username, password } }),
      "auth login",
    );

    await jsonOrThrow(
      await api.put("/api/v1/admin/runtime-settings/providers/openai", {
        data: { credential: E2E_PROVIDER_CREDENTIAL },
      }),
      "provider credential",
    );

    const domainsBody = (await jsonOrThrow(
      await api.get("/api/v1/admin/domains"),
      "list domains",
    )) as { domains?: DomainRow[] };
    let domain = domainsBody.domains?.find((row) => row.id === E2E_DOMAIN_ID);

    if (!domain) {
      const created = await api.post("/api/v1/admin/domains", {
        data: {
          id: E2E_DOMAIN_ID,
          displayName: E2E_DOMAIN_DISPLAY_NAME,
          embeddingProfileId: "openai-embedding-default",
        },
      });
      if (created.status() !== 201 && created.status() !== 200 && created.status() !== 409) {
        await jsonOrThrow(created, "domain create");
      }
      const refreshed = (await jsonOrThrow(
        await api.get("/api/v1/admin/domains"),
        "list domains after create",
      )) as { domains?: DomainRow[] };
      domain = refreshed.domains?.find((row) => row.id === E2E_DOMAIN_ID);
    }

    await ensureDomainStarted(api, domain);

    const existingReady = await findReadySource(api, E2E_DOMAIN_ID);
    const fixtureBytes = fs.readFileSync(FIXTURE_PATH);
    const markdownSourceId = await ensureNamedSource(api, {
      filename: E2E_PREVIEW_MARKDOWN_NAME,
      mimeType: "text/markdown",
      buffer: fixtureBytes,
      waitReady: !existingReady,
    });

    const pdfBytes = fs.readFileSync(PDF_FIXTURE_PATH);
    const pdfSourceId = await ensureNamedSource(api, {
      filename: E2E_PREVIEW_PDF_NAME,
      mimeType: "application/pdf",
      buffer: pdfBytes,
      waitReady: false,
    });

    const info: SeedInfo = {
      domainId: E2E_DOMAIN_ID,
      displayName: domain?.displayName ?? E2E_DOMAIN_DISPLAY_NAME,
      markdownSourceId,
      pdfSourceId,
    };
    writeSeedInfo(info);
    return info;
  } finally {
    await api.dispose();
  }
}
