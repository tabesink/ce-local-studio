/**
 * Pure helpers for Settings → Knowledge Domains (F-009 deploy + lifecycle).
 * Kept free of React / path aliases so node:test can import them directly.
 */

/** Mirrors backend DOMAIN_ID_PATTERN in context_engine.services.domains. */
export const DOMAIN_ID_PATTERN = /^[a-z0-9][a-z0-9_-]{1,62}$/;

export type DomainUiTone = "default" | "good" | "warning" | "danger" | "info";

export type EmbeddingProfileLike = {
  id: string;
  name?: string;
  profileKind: string;
  /** Optional; generated ModelProfileDto has no isDefault — first embedding wins when absent. */
  isDefault?: boolean;
  supportsGraphExtraction?: boolean;
};

export type DeployDomainInput = {
  id: string;
  displayName: string;
  embeddingProfileId: string;
  graphExtractionProfileId: string;
};

export type DeployDomainApi = {
  createDomain: (input: DeployDomainInput) => Promise<{ id: string }>;
  startDomain: (domainId: string) => Promise<unknown>;
};

export type DeployOutcome =
  | { kind: "success" }
  | { kind: "create_failed"; error: unknown }
  | { kind: "start_failed_keep"; error: unknown };

export type DomainBusyAction = "start" | "stop" | "delete" | "deploy";

export type StorageComponentLike = {
  kind: string;
  label: string;
  bytes: number;
  percent: number;
};

export type StorageSummaryLike = {
  limitBytes: number;
  totalBytes: number;
  totalPercent: number;
  warning: string;
  components: StorageComponentLike[];
};

/** DTO/field tokens that must not appear in Domains Settings UI source. */
export const FORBIDDEN_DOMAIN_UI_FIELD_TOKENS = [
  "host_port",
  "hostPort",
  "container_id",
  "containerId",
  "runtime_url",
  "runtimeUrl",
  "base_url",
  "baseUrl",
  "compose_project",
  "composeProject",
] as const;

export function isValidDomainId(id: string): boolean {
  return DOMAIN_ID_PATTERN.test(id.trim());
}

export function filterEmbeddingProfiles<T extends EmbeddingProfileLike>(profiles: T[]): T[] {
  return profiles.filter((profile) => profile.profileKind === "embedding");
}

export function filterGraphExtractionProfiles<T extends EmbeddingProfileLike>(profiles: T[]): T[] {
  return profiles.filter(
    (profile) => profile.profileKind === "synthesis" && profile.supportsGraphExtraction === true,
  );
}

export function defaultEmbeddingProfileId(profiles: EmbeddingProfileLike[]): string | null {
  const embedding = filterEmbeddingProfiles(profiles);
  if (embedding.length === 0) return null;
  const preferred = embedding.find((profile) => profile.isDefault);
  return (preferred ?? embedding[0]).id;
}

export function defaultGraphExtractionProfileId(profiles: EmbeddingProfileLike[]): string | null {
  const extraction = filterGraphExtractionProfiles(profiles);
  if (extraction.length === 0) return null;
  const preferred = extraction.find((profile) => profile.isDefault);
  return (preferred ?? extraction[0]).id;
}

/** Safe expanded-row label — profile name when known, else id, else Locked. Never a URL. */
export function embeddingProfileLabel(
  embeddingProfileId: string | null | undefined,
  profiles: EmbeddingProfileLike[],
): string {
  const id = embeddingProfileId?.trim() ?? "";
  if (!id) return "Locked";
  const match = profiles.find((profile) => profile.id === id);
  const name = match?.name?.trim();
  if (name) return name;
  return id;
}

/** Accordion expand toggle — one open row at a time (or collapse current). */
export function nextExpandedDomainId(current: string | null, toggledId: string): string | null {
  return current === toggledId ? null : toggledId;
}

export function canDeployDomain(input: {
  id: string;
  displayName: string;
  embeddingProfileId: string;
  graphExtractionProfileId: string;
  hasEmbeddingProfiles: boolean;
  hasGraphExtractionProfiles: boolean;
}): boolean {
  return (
    input.hasEmbeddingProfiles &&
    input.hasGraphExtractionProfiles &&
    isValidDomainId(input.id) &&
    input.displayName.trim().length > 0 &&
    input.embeddingProfileId.trim().length > 0 &&
    input.graphExtractionProfileId.trim().length > 0
  );
}

/**
 * Create then start. On start failure after create, keep the domain
 * (start_failed_keep) — never auto-delete.
 */
export async function deployDomain(
  input: DeployDomainInput,
  api: DeployDomainApi,
): Promise<DeployOutcome> {
  let created: { id: string };
  try {
    created = await api.createDomain({
      id: input.id.trim(),
      displayName: input.displayName.trim(),
      embeddingProfileId: input.embeddingProfileId.trim(),
      graphExtractionProfileId: input.graphExtractionProfileId.trim(),
    });
  } catch (error) {
    return { kind: "create_failed", error };
  }

  try {
    await api.startDomain(created.id);
    return { kind: "success" };
  } catch (error) {
    return { kind: "start_failed_keep", error };
  }
}

export function domainTone(state: string): DomainUiTone {
  if (state === "running") return "good";
  if (state === "error") return "danger";
  if (state === "stopped") return "default";
  return "warning";
}

export function busyLabel(action: DomainBusyAction): string {
  switch (action) {
    case "start":
      return "starting";
    case "stop":
      return "stopping";
    case "delete":
      return "deleting";
    case "deploy":
      return "deploying";
  }
}

/**
 * Start XOR Stop for the row header.
 * Returns null when no primary lifecycle control should show (e.g. deleting).
 */
export function primaryLifecycleAction(state: string): "start" | "stop" | null {
  if (state === "deleting") return null;
  return state === "running" ? "stop" : "start";
}

/** Delete confirm gate — cancel must not call deleteDomain. */
export function shouldRequestDelete(confirmed: boolean): boolean {
  return confirmed;
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"] as const;
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  const digits = value >= 10 || index === 0 ? 0 : 1;
  return `${value.toFixed(digits).replace(/\.0$/, "")} ${units[index]}`;
}

export function clampStoragePercent(percent: number): number {
  if (!Number.isFinite(percent) || percent <= 0) return 0;
  return Math.min(100, Math.max(1, Math.round(percent)));
}

export function storageTone(warning: string): DomainUiTone {
  if (warning === "exceeded") return "danger";
  if (warning === "near_limit") return "warning";
  return "default";
}

export function storageWarningLabel(warning: string): string {
  if (warning === "near_limit") return "near limit";
  if (warning === "exceeded") return "exceeded";
  return "ok";
}

export function storageLimitLabel(summary: StorageSummaryLike): string {
  return `${formatBytes(summary.totalBytes)} of ${formatBytes(summary.limitBytes)}`;
}
