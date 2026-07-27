"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Database, KeyRound, Palette, Users } from "lucide-react";
import {
  EmptySafeNotice,
  Input,
  PageState,
  Select,
  SettingsButton,
  SettingsFactRows,
  SettingsGroup,
  SettingsInput,
  SettingsLayout,
  SettingsNotice,
  StatusPill,
  ToggleSwitch,
  UiModal,
  UiModalHeader,
  type SettingsSectionDef,
} from "@/components/ui";
import { isApiError } from "@/lib/api/errors";
import { useAuthStore } from "@/features/auth/auth-store";
import { DomainAccordionRow } from "@/features/settings-panel/DomainAccordionRow";
import { SettingsRow } from "@/features/settings-panel/SettingsRow";
import { PreferencesPanel } from "@/features/user-preferences/PreferencesPanel";
import {
  getRuntimeSettings,
  listUsers,
  patchRuntimeSettings,
  rotateProviderCredential,
  type ModelProfile,
  type RuntimeSettingsSnapshot,
} from "@/features/settings-panel/api";
import {
  createDomain,
  deleteDomain,
  listAdminDomains,
  startDomain,
  stopDomain,
  type AdminDomain,
} from "@/features/domains/api";
import {
  canDeployDomain,
  defaultEmbeddingProfileId,
  deployDomain,
  filterEmbeddingProfiles,
  isValidDomainId,
  nextExpandedDomainId,
  primaryLifecycleAction,
  shouldRequestDelete,
  type DomainBusyAction,
} from "@/features/settings-panel/domainSettingsHelpers";
import type { CurrentUser } from "@/types/auth";

type SectionId = "general" | "provider" | "domains" | "users";

const ALLOWED_SECTIONS: readonly SectionId[] = ["general", "provider", "domains", "users"];
const ADMIN_SECTIONS: readonly SectionId[] = ["provider", "domains", "users"];

function errorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  return "Request failed.";
}

function parseSectionParam(raw: string | null): SectionId | null {
  if (!raw) return null;
  return (ALLOWED_SECTIONS as readonly string[]).includes(raw) ? (raw as SectionId) : null;
}

function domainStateTone(state: AdminDomain["state"]): "default" | "good" | "warning" | "danger" {
  if (state === "running") return "good";
  if (state === "deleting") return "warning";
  return "default";
}

function domainStateLabel(state: AdminDomain["state"]): string {
  if (state === "running") return "Running";
  if (state === "deleting") return "Deleting";
  return "Stopped";
}

/* Controllers-style Settings Domains accordion (cite environment-controls).
   Controller/storage/hardware/plugins/skills sections stay absent (F-010). */
export function SettingsPanel() {
  return (
    <Suspense fallback={<PageState title="Settings" message="Loading settings…" />}>
      <SettingsPanelInner />
    </Suspense>
  );
}

function SettingsPanelInner() {
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.role === "administrator";
  const router = useRouter();
  const searchParams = useSearchParams();
  const [sectionNotice, setSectionNotice] = useState<string | null>(null);
  const [runtime, setRuntime] = useState<RuntimeSettingsSnapshot | null>(null);
  const [domains, setDomains] = useState<AdminDomain[]>([]);
  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const sections = useMemo<SettingsSectionDef<SectionId>[]>(() => {
    const rows: SettingsSectionDef<SectionId>[] = [
      { id: "general", label: "General", description: "Personal preferences", icon: <Palette className="h-3.5 w-3.5" /> },
    ];
    if (isAdmin) {
      rows.push(
        { id: "provider", label: "Model Provider", description: "Providers and model profiles", icon: <KeyRound className="h-3.5 w-3.5" /> },
        { id: "domains", label: "Knowledge Domains", description: "Domain-backed retrieval", icon: <Database className="h-3.5 w-3.5" /> },
        { id: "users", label: "Users", description: "User accounts", icon: <Users className="h-3.5 w-3.5" /> },
      );
    }
    return rows;
  }, [isAdmin]);

  const allowedSectionIds = useMemo(
    () => new Set(sections.map((row) => row.id)),
    [sections],
  );

  const section = useMemo<SectionId>(() => {
    const requested = parseSectionParam(searchParams.get("section"));
    if (!requested) return "general";
    if (!allowedSectionIds.has(requested)) return "general";
    return requested;
  }, [allowedSectionIds, searchParams]);

  useEffect(() => {
    const raw = searchParams.get("section");
    const requested = parseSectionParam(raw);
    if (raw && !requested) {
      setSectionNotice("That settings section is not available. Showing General.");
      const params = new URLSearchParams(searchParams.toString());
      params.delete("section");
      const query = params.toString();
      router.replace(query ? `/settings?${query}` : "/settings");
      return;
    }
    if (requested && !allowedSectionIds.has(requested)) {
      setSectionNotice("That settings section is not available for your account. Showing General.");
      const params = new URLSearchParams(searchParams.toString());
      params.delete("section");
      const query = params.toString();
      router.replace(query ? `/settings?${query}` : "/settings");
      return;
    }
    if (requested && allowedSectionIds.has(requested)) {
      setSectionNotice(null);
    }
  }, [allowedSectionIds, router, searchParams]);

  useEffect(() => {
    if (!isAdmin) {
      setRuntime(null);
      setDomains([]);
      setUsers([]);
    }
  }, [isAdmin]);

  const selectSection = useCallback(
    (next: SectionId) => {
      if (!allowedSectionIds.has(next)) return;
      const params = new URLSearchParams(searchParams.toString());
      if (next === "general") params.delete("section");
      else params.set("section", next);
      const query = params.toString();
      const href = query ? `/settings?${query}` : "/settings";
      if (next === "general" && !searchParams.get("section")) {
        router.replace(href);
        return;
      }
      if (ADMIN_SECTIONS.includes(next) || next === "general") {
        if (next === "general") router.replace(href);
        else router.push(href);
      }
    },
    [allowedSectionIds, router, searchParams],
  );

  const reload = useCallback(async (opts?: { clearError?: boolean }) => {
    setLoading(true);
    if (opts?.clearError !== false) setError(null);
    try {
      if (isAdmin) {
        const [runtimeSnapshot, domainRows, userRows] = await Promise.all([
          getRuntimeSettings(),
          listAdminDomains(),
          listUsers(),
        ]);
        setRuntime(runtimeSnapshot);
        setDomains(domainRows);
        setUsers(userRows);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return (
    <SettingsLayout<SectionId>
      sections={sections}
      activeSection={section}
      onSelectSection={selectSection}
      title="Settings"
      status={loading ? "Loading" : ""}
      loading={loading}
      onReload={() => void reload()}
    >
      {sectionNotice ? <SettingsNotice tone="warning" className="mb-4">{sectionNotice}</SettingsNotice> : null}
      {error ? <SettingsNotice tone="danger" className="mb-4">{error}</SettingsNotice> : null}
      {notice ? <SettingsNotice tone="good" className="mb-4">{notice}</SettingsNotice> : null}
      {section === "general" ? <PreferencesPanel /> : null}
      {section === "provider" && isAdmin ? (
        <ProviderSection
          runtime={runtime}
          onChanged={(message) => {
            setNotice(message);
            void reload();
          }}
          onError={(message) => setError(message)}
        />
      ) : null}
      {section === "domains" && isAdmin ? (
        <DomainsSection
          domains={domains}
          modelProfiles={runtime?.modelProfiles ?? []}
          onChanged={(message) => {
            setError(null);
            setNotice(message);
            void reload();
          }}
          onError={(message) => {
            setNotice(null);
            setError(message);
          }}
          reload={() => reload({ clearError: false })}
        />
      ) : null}
      {section === "users" && isAdmin ? <UsersSection users={users} /> : null}
    </SettingsLayout>
  );
}

function ProviderSection({
  runtime,
  onChanged,
  onError,
}: {
  runtime: RuntimeSettingsSnapshot | null;
  onChanged: (message: string) => void;
  onError: (message: string) => void;
}) {
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);

  if (!runtime) return <EmptySafeNotice>Runtime settings are unavailable.</EmptySafeNotice>;

  const rotate = async (providerKind: string) => {
    const credential = credentials[providerKind]?.trim();
    if (!credential) return;
    setSaving(providerKind);
    try {
      await rotateProviderCredential(providerKind, credential);
      setCredentials((current) => ({ ...current, [providerKind]: "" }));
      onChanged(`Credential updated for ${providerKind}.`);
    } catch (err) {
      onError(errorMessage(err));
    } finally {
      setSaving(null);
    }
  };

  const setSynthesisProfile = async (profileId: string) => {
    try {
      await patchRuntimeSettings({ activeSynthesisProfileId: profileId });
      onChanged("Active synthesis profile updated.");
    } catch (err) {
      onError(errorMessage(err));
    }
  };

  return (
    <>
      <SettingsGroup title="Providers" description="Credentials are write-only; values are never displayed.">
        {runtime.providers.map((provider) => (
          <SettingsRow
            key={provider.providerKind}
            label={provider.providerKind}
            status={
              <StatusPill tone={provider.isConfigured ? "good" : "warning"}>
                {provider.isConfigured ? "Configured" : "Not configured"}
              </StatusPill>
            }
            control={
              <div className="flex w-full items-center justify-end gap-1.5">
                <SettingsInput
                  type="password"
                  value={credentials[provider.providerKind] ?? ""}
                  onChange={(value) =>
                    setCredentials((current) => ({ ...current, [provider.providerKind]: value }))
                  }
                  placeholder="New credential"
                  aria-label={`New credential for ${provider.providerKind}`}
                  className="max-w-56"
                />
                <SettingsButton
                  tone="primary"
                  disabled={saving === provider.providerKind || !(credentials[provider.providerKind] ?? "").trim()}
                  onClick={() => void rotate(provider.providerKind)}
                >
                  Rotate
                </SettingsButton>
              </div>
            }
          />
        ))}
      </SettingsGroup>

      <SettingsGroup title="Model profiles">
        {runtime.modelProfiles.length === 0 ? (
          <EmptySafeNotice>No model profiles configured.</EmptySafeNotice>
        ) : (
          runtime.modelProfiles.map((profile) => {
            const isActiveSynthesis = profile.id === runtime.runtimeSettings.activeSynthesisProfileId;
            return (
              <SettingsRow
                key={profile.id}
                label={profile.name}
                description={`${profile.profileKind} - ${profile.providerKind} - ${profile.modelName}`}
                status={
                  isActiveSynthesis ? <StatusPill tone="info">Active synthesis</StatusPill> : undefined
                }
                actions={
                  profile.profileKind === "synthesis" && !isActiveSynthesis ? (
                    <SettingsButton onClick={() => void setSynthesisProfile(profile.id)}>Make active</SettingsButton>
                  ) : undefined
                }
              />
            );
          })
        )}
      </SettingsGroup>

      <SettingsGroup title="Document parser">
        <SettingsFactRows
          rows={[{ label: "Active parser", value: runtime.runtimeSettings.activeParserKind, mono: true }]}
        />
      </SettingsGroup>
    </>
  );
}

function DomainsSection({
  domains,
  modelProfiles,
  onChanged,
  onError,
  reload,
}: {
  domains: AdminDomain[];
  modelProfiles: ModelProfile[];
  onChanged: (message: string) => void;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const embeddingProfiles = useMemo(() => filterEmbeddingProfiles(modelProfiles), [modelProfiles]);
  const [draftId, setDraftId] = useState("");
  const [draftName, setDraftName] = useState("");
  const [draftEmbeddingId, setDraftEmbeddingId] = useState(() => defaultEmbeddingProfileId(embeddingProfiles) ?? "");
  const [busy, setBusy] = useState<{ id: string; action: DomainBusyAction } | null>(null);
  const [pendingDelete, setPendingDelete] = useState<AdminDomain | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (!draftEmbeddingId || !embeddingProfiles.some((profile) => profile.id === draftEmbeddingId)) {
      setDraftEmbeddingId(defaultEmbeddingProfileId(embeddingProfiles) ?? "");
    }
  }, [draftEmbeddingId, embeddingProfiles]);

  useEffect(() => {
    if (expandedId && !domains.some((domain) => domain.id === expandedId)) {
      setExpandedId(null);
    }
    if (pendingDelete && !domains.some((domain) => domain.id === pendingDelete.id)) {
      setPendingDelete(null);
    }
  }, [domains, expandedId, pendingDelete]);

  const deployEnabled = canDeployDomain({
    id: draftId,
    displayName: draftName,
    embeddingProfileId: draftEmbeddingId,
    hasEmbeddingProfiles: embeddingProfiles.length > 0,
  });

  const run = async (
    domain: AdminDomain,
    action: "start" | "stop" | "delete",
  ) => {
    setBusy({ id: domain.id, action });
    try {
      if (action === "start") await startDomain(domain.id);
      if (action === "stop") await stopDomain(domain.id);
      if (action === "delete") await deleteDomain(domain.id, domain.version);
      onChanged(`Knowledge Domain ${domain.id}: ${action} requested.`);
      await reload();
    } catch (err) {
      onError(errorMessage(err));
      await reload();
    } finally {
      setBusy((current) => (current?.id === domain.id ? null : current));
    }
  };

  const onDeploy = async () => {
    if (!deployEnabled) return;
    if (!isValidDomainId(draftId)) {
      onError("Domain id must be 2-63 characters: lowercase letters, digits, underscore, or hyphen.");
      return;
    }
    setBusy({ id: "__deploy__", action: "deploy" });
    try {
      const outcome = await deployDomain(
        {
          id: draftId,
          displayName: draftName,
          embeddingProfileId: draftEmbeddingId,
        },
        { createDomain, startDomain },
      );
      if (outcome.kind === "success") {
        setDraftId("");
        setDraftName("");
        setDraftEmbeddingId(defaultEmbeddingProfileId(embeddingProfiles) ?? "");
        onChanged(`Knowledge Domain ${draftId.trim()}: deploy requested.`);
        await reload();
        return;
      }
      if (outcome.kind === "create_failed") {
        onError(errorMessage(outcome.error));
        return;
      }
      // start_failed_keep: keep domain, clear draft so retry is Start (not Deploy again)
      setDraftId("");
      setDraftName("");
      setDraftEmbeddingId(defaultEmbeddingProfileId(embeddingProfiles) ?? "");
      onError(
        "The Knowledge Domain was created, but start did not finish. Try Start again. " +
          errorMessage(outcome.error),
      );
      await reload();
    } finally {
      setBusy((current) => (current?.id === "__deploy__" ? null : current));
    }
  };

  const confirmDelete = () => {
    if (!pendingDelete || !shouldRequestDelete(true)) return;
    const target = pendingDelete;
    setPendingDelete(null);
    void run(target, "delete");
  };

  const anyBusy = busy !== null;
  const deployBusy = busy?.id === "__deploy__";

  return (
    <>
      <SettingsGroup
        title="Knowledge Domains"
        description="Lifecycle on backend. No Docker details in UI."
      >
        {domains.length === 0 ? (
          <EmptySafeNotice>No Knowledge Domains are available.</EmptySafeNotice>
        ) : (
          domains.map((domain) => {
            const lifecycle = primaryLifecycleAction(domain.state);
            const expanded = expandedId === domain.id;
            const panelId = `knowledge-domain-${domain.id}-panel`;
            const embeddingLabel = domain.embeddingProfile.name?.trim() || domain.embeddingProfile.id;
            return (
              <DomainAccordionRow
                key={domain.id}
                displayName={domain.displayName}
                domainId={domain.id}
                expanded={expanded}
                panelId={panelId}
                stateLabel={domainStateLabel(domain.state)}
                stateTone={domainStateTone(domain.state)}
                onToggleExpand={() => setExpandedId((current) => nextExpandedDomainId(current, domain.id))}
                lifecycleControl={
                  <ToggleSwitch
                    checked={lifecycle === "stop"}
                    aria-label={`${lifecycle === "stop" ? "Stop" : "Start"} ${domain.displayName}`}
                    title={lifecycle === "stop" ? "Stop Knowledge Domain" : "Start Knowledge Domain"}
                    disabled={anyBusy || lifecycle === null || domain.state === "deleting"}
                    onCheckedChange={() => {
                      if (lifecycle) void run(domain, lifecycle);
                    }}
                  />
                }
              >
                <div className="space-y-3">
                  <div className="flex gap-3">
                    <div className="w-7 shrink-0" aria-hidden />
                    <div className="min-w-0 flex-1 space-y-3">
                      <label className="grid gap-1.5">
                        <span className="text-[length:var(--fs-xs)] text-(--ui-muted)">Embedding model</span>
                        <Input
                          value={`${embeddingLabel} · ${domain.embeddingProfile.vectorDimensions}d · locked`}
                          readOnly
                          aria-label={`${domain.displayName} embedding model`}
                          className="h-7 cursor-default font-mono text-(--ui-muted) focus:border-(--ui-separator) focus:ring-0"
                        />
                      </label>
                      <SettingsFactRows
                        rows={[
                          {
                            label: "Query eligible",
                            value: domain.queryEligible ? "Yes" : "No",
                            status: {
                              tone: domain.queryEligible ? "good" : "default",
                              label: domain.queryEligible ? "Eligible" : "Not eligible",
                            },
                          },
                          {
                            label: "Runtime ready",
                            value: domain.runtimeReady ? "Yes" : "No",
                            status: {
                              tone: domain.runtimeReady ? "good" : "warning",
                              label: domain.runtimeReady ? "Ready" : "Not ready",
                            },
                          },
                          {
                            label: "Control generation",
                            value: String(domain.controlGeneration),
                            mono: true,
                            dim: true,
                          },
                          {
                            label: "Version",
                            value: String(domain.version),
                            mono: true,
                            dim: true,
                          },
                        ]}
                      />
                    </div>
                    <div className="w-9 shrink-0" aria-hidden />
                  </div>
                  <div className="flex gap-3">
                    <div className="w-7 shrink-0" aria-hidden />
                    <div className="min-w-0 flex-1" aria-hidden />
                    <div className="shrink-0">
                      <SettingsButton
                        tone="danger"
                        disabled={anyBusy || domain.state === "deleting"}
                        onClick={() => setPendingDelete(domain)}
                      >
                        Delete
                      </SettingsButton>
                    </div>
                  </div>
                </div>
              </DomainAccordionRow>
            );
          })
        )}
      </SettingsGroup>

      <SettingsGroup
        title="New Knowledge Domain"
        description="Create and start a domain-backed retrieval domain."
      >
        <div className="flex flex-wrap items-center gap-2 px-3.5 py-2.5">
          <SettingsInput
            value={draftName}
            onChange={setDraftName}
            placeholder="Name"
            aria-label="New Knowledge Domain display name"
            className="w-32 shrink-0"
          />
          <SettingsInput
            value={draftId}
            onChange={setDraftId}
            placeholder="id"
            aria-label="New Knowledge Domain id"
            className="w-28 shrink-0 font-mono"
          />
          <div className="min-w-40 flex-1">
            <Select
              value={draftEmbeddingId}
              onChange={(event) => setDraftEmbeddingId(event.target.value)}
              disabled={embeddingProfiles.length === 0 || anyBusy}
              aria-label="Embedding model"
              options={
                embeddingProfiles.length === 0
                  ? [{ value: "", label: "No embedding profiles" }]
                  : embeddingProfiles.map((profile) => ({ value: profile.id, label: profile.name }))
              }
              className="h-7"
            />
          </div>
          <SettingsButton disabled={!deployEnabled || anyBusy} onClick={() => void onDeploy()}>
            {deployBusy ? "Deploying…" : "Deploy"}
          </SettingsButton>
          {embeddingProfiles.length === 0 ? (
            <span className="min-w-full text-[length:var(--fs-sm)] text-(--ui-muted)">
              Add an embedding model profile before deploying a Knowledge Domain.
            </span>
          ) : null}
        </div>
      </SettingsGroup>

      <UiModal isOpen={pendingDelete !== null} onClose={() => setPendingDelete(null)} maxWidth="max-w-md">
        <UiModalHeader title="Delete Knowledge Domain" onClose={() => setPendingDelete(null)} />
        <div className="space-y-4 px-6 py-4">
          <p className="text-[length:var(--fs-base)] text-(--ui-fg)">
            Delete Knowledge Domain &ldquo;{pendingDelete?.displayName}&rdquo;? This cannot be undone.
          </p>
          <div className="flex justify-end gap-2">
            <SettingsButton onClick={() => setPendingDelete(null)}>Cancel</SettingsButton>
            <SettingsButton tone="danger" onClick={confirmDelete}>
              Delete
            </SettingsButton>
          </div>
        </div>
      </UiModal>
    </>
  );
}

function UsersSection({ users }: { users: CurrentUser[] }) {
  return (
    <SettingsGroup title="Users" description="Read-only account status.">
      {users.length === 0 ? (
        <EmptySafeNotice>No users found.</EmptySafeNotice>
      ) : (
        users.map((row) => (
          <SettingsRow
            key={row.id}
            label={row.displayName}
            value={<span className="text-[length:var(--fs-sm)] text-[var(--dim)]">{row.role}</span>}
            status={
              row.disabled ? <StatusPill tone="danger">Disabled</StatusPill> : <StatusPill tone="good">Active</StatusPill>
            }
          />
        ))
      )}
    </SettingsGroup>
  );
}
