/* CE adapter for Settings admin runtime-settings surfaces.

   GET   /api/v1/admin/runtime-settings
   PUT   /api/v1/admin/runtime-settings/providers/{kind}
   PATCH /api/v1/admin/runtime-settings
   POST  /api/v1/admin/runtime-settings/model-profiles
   PATCH /api/v1/admin/runtime-settings/model-profiles/{id}
   DELETE /api/v1/admin/runtime-settings/model-profiles/{id}
   GET   /api/v1/admin/users
*/

import { ceFetch, ifMatchHeader, idempotencyKeyHeader } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/openapi";
import type { CurrentUser } from "@/types/auth";

type ModelProfileCreateRequest = components["schemas"]["ModelProfileCreateRequest"];
type ModelProfilePatchRequest = components["schemas"]["ModelProfilePatchRequest"];
type ProviderCredentialRequest = components["schemas"]["ProviderCredentialRequest"];
type RuntimeSettingsPatchRequest = components["schemas"]["RuntimeSettingsPatchRequest"];

export type ProviderSummary = components["schemas"]["ProviderSummaryDto"];
export type ModelProfile = components["schemas"]["ModelProfileDto"];
export type RuntimeSettings = components["schemas"]["RuntimeSettingsDto"];
export type RuntimeSettingsSnapshot = components["schemas"]["RuntimeSettingsSnapshotResponse"];

/** @deprecated Use ProviderSummary (generated ProviderSummaryDto). */
export type ProviderStatus = ProviderSummary;

export async function getRuntimeSettings(): Promise<RuntimeSettingsSnapshot> {
  return ceFetch<RuntimeSettingsSnapshot>("/admin/runtime-settings");
}

export async function rotateProviderCredential(
  kind: ProviderSummary["kind"] | string,
  credential: string,
  version: number,
): Promise<ProviderSummary> {
  const headers = ifMatchHeader(version);
  if (!headers) {
    throw new Error("Provider version is required for credential replacement (If-Match).");
  }
  const payload: ProviderCredentialRequest = { credential };
  const body = await ceFetch<components["schemas"]["ProviderMutationResponse"]>(
    `/admin/runtime-settings/providers/${encodeURIComponent(kind)}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers,
    },
  );
  return body.provider;
}

export async function patchRuntimeSettings(
  patch: RuntimeSettingsPatchRequest,
  version: number,
): Promise<RuntimeSettings> {
  const headers = ifMatchHeader(version);
  if (!headers) {
    throw new Error("Runtime settings version is required for patch (If-Match).");
  }
  const body = await ceFetch<components["schemas"]["RuntimeSettingsMutationResponse"]>("/admin/runtime-settings", {
    method: "PATCH",
    body: JSON.stringify(patch),
    headers,
  });
  return body.runtimeSettings;
}

export async function createModelProfile(
  input: ModelProfileCreateRequest,
  idempotencyKey: string,
): Promise<ModelProfile> {
  const headers = idempotencyKeyHeader(idempotencyKey);
  if (!headers) {
    throw new Error("Idempotency-Key is required for model-profile create.");
  }
  const body = await ceFetch<components["schemas"]["ModelProfileMutationResponse"]>(
    "/admin/runtime-settings/model-profiles",
    {
      method: "POST",
      body: JSON.stringify(input),
      headers,
    },
  );
  return body.modelProfile;
}

export async function patchModelProfile(
  profileId: string,
  patch: ModelProfilePatchRequest,
  version: number,
): Promise<ModelProfile> {
  const headers = ifMatchHeader(version);
  if (!headers) {
    throw new Error("Model profile version is required for patch (If-Match).");
  }
  const body = await ceFetch<components["schemas"]["ModelProfileMutationResponse"]>(
    `/admin/runtime-settings/model-profiles/${encodeURIComponent(profileId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(patch),
      headers,
    },
  );
  return body.modelProfile;
}

export async function deleteModelProfile(profileId: string): Promise<void> {
  await ceFetch<void>(`/admin/runtime-settings/model-profiles/${encodeURIComponent(profileId)}`, {
    method: "DELETE",
  });
}

export async function listUsers(): Promise<CurrentUser[]> {
  const body = await ceFetch<{ users: CurrentUser[] }>("/admin/users");
  return body.users;
}
