/* CE adapter for the LS settings-panel slice.
   Wires only CE-contracted admin surfaces (P1/P2/P3):

   GET   /api/v1/admin/runtime-settings
   PUT   /api/v1/admin/runtime-settings/providers/{providerKind}
   PATCH /api/v1/admin/runtime-settings
   POST  /api/v1/admin/runtime-settings/model-profiles
   PATCH /api/v1/admin/runtime-settings/model-profiles/{id}
   DELETE /api/v1/admin/runtime-settings/model-profiles/{id}
   GET   /api/v1/admin/users

   Controller, storage, hardware, plugins, and skills sections are F-010 gated. */

import { ceFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/openapi";
import type { CurrentUser } from "@/types/auth";

type ModelProfileCreateRequest = components["schemas"]["ModelProfileCreateRequest"];
type ProviderCredentialRequest = components["schemas"]["ProviderCredentialRequest"];
type RuntimeSettingsPatchRequest = components["schemas"]["RuntimeSettingsPatchRequest"];

export type ProviderStatus = {
  providerKind: string;
  isConfigured: boolean;
};

export type ModelProfile = {
  id: string;
  name: string;
  profileKind: string;
  providerKind: string;
  modelName: string;
  vectorDimensions: number | null;
  isDefault: boolean;
};

export type RuntimeSettings = {
  activeSynthesisProfileId: string | null;
  activeParserKind: string;
};

export type RuntimeSettingsSnapshot = {
  providers: ProviderStatus[];
  modelProfiles: ModelProfile[];
  runtimeSettings: RuntimeSettings;
};

export async function getRuntimeSettings(): Promise<RuntimeSettingsSnapshot> {
  return ceFetch<RuntimeSettingsSnapshot>("/admin/runtime-settings");
}

export async function rotateProviderCredential(providerKind: string, credential: string): Promise<ProviderStatus> {
  const payload: ProviderCredentialRequest = { credential };
  const body = await ceFetch<{ provider: ProviderStatus }>(`/admin/runtime-settings/providers/${providerKind}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return body.provider;
}

export async function patchRuntimeSettings(patch: RuntimeSettingsPatchRequest): Promise<RuntimeSettings> {
  const body = await ceFetch<{ runtimeSettings: RuntimeSettings }>("/admin/runtime-settings", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  return body.runtimeSettings;
}

export async function createModelProfile(input: ModelProfileCreateRequest): Promise<ModelProfile> {
  const body = await ceFetch<{ modelProfile: ModelProfile }>("/admin/runtime-settings/model-profiles", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return body.modelProfile;
}

export async function deleteModelProfile(profileId: string): Promise<void> {
  await ceFetch<void>(`/admin/runtime-settings/model-profiles/${profileId}`, { method: "DELETE" });
}

export async function listUsers(): Promise<CurrentUser[]> {
  const body = await ceFetch<{ users: CurrentUser[] }>("/admin/users");
  return body.users;
}
