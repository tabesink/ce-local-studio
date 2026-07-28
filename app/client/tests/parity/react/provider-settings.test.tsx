import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SettingsGroup } from "@/_shared/ui";
import { StatusPill } from "@/ui";
import { SettingsRow } from "@/features/settings-panel/SettingsRow";

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

function ProviderSettingsTarget() {
  return (
    <div data-testid="provider-settings-target">
      <h2>Model Provider</h2>
      <p>Provider access and the system-wide synthesis default.</p>
      <SettingsGroup title="Providers" description="Credentials are write-only; values are never displayed.">
        <SettingsRow
          label="OpenAI"
          description="Synthesis and embedding profiles"
          status={<StatusPill tone="good">Configured</StatusPill>}
          control={<button type="button">Replace credential</button>}
        />
        <SettingsRow
          label="AWS Bedrock"
          description="Synthesis and embedding profiles"
          status={<StatusPill tone="warning">Not configured</StatusPill>}
          control={<button type="button">Add credential</button>}
        />
        <SettingsRow
          label="Ollama"
          description="Local provider; runtime wiring is operator-managed"
          status={<StatusPill tone="default">No browser credential</StatusPill>}
        />
      </SettingsGroup>
      <SettingsGroup title="Synthesis default" description="Applies to new direct and grounded turns for all users.">
        <SettingsRow
          label="Active model"
          description="In-flight work keeps its resolved configuration"
          control={
            <select aria-label="Active synthesis model" defaultValue="synth-a">
              <option value="synth-a">OpenAI · Synthetic Mini</option>
              <option value="synth-b" disabled>
                Bedrock · Synthetic — provider required
              </option>
            </select>
          }
        />
      </SettingsGroup>
      <SettingsGroup
        title="Embedding profiles"
        description="Available when an administrator deploys a Knowledge Domain."
      >
        <SettingsRow
          label="OpenAI Default Embedding"
          description="text-embedding-3-small"
          value={<span>1536 dimensions · locked at domain create</span>}
        />
      </SettingsGroup>
    </div>
  );
}

describe("Provider settings parity (P9-07 U5)", () => {
  it("renders compact provider rows, synthesis selector, and embedding facts in both themes", () => {
    const { rerender } = render(
      <ThemeWrap theme="zai-dark">
        <ProviderSettingsTarget />
      </ThemeWrap>,
    );
    expect(screen.getByTestId("provider-settings-target")).toBeInTheDocument();
    expect(screen.getByText("Model Provider")).toBeInTheDocument();
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("Configured")).toBeInTheDocument();
    expect(screen.getByText("Not configured")).toBeInTheDocument();
    expect(screen.getByText("Ollama")).toBeInTheDocument();
    expect(screen.getByLabelText("Active synthesis model")).toBeInTheDocument();
    expect(screen.getByText(/locked at domain create/i)).toBeInTheDocument();
    expect(screen.queryByText(/runtime-ready/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /create model profile/i })).not.toBeInTheDocument();

    rerender(
      <ThemeWrap theme="zai-light">
        <ProviderSettingsTarget />
      </ThemeWrap>,
    );
    expect(screen.getByText("AWS Bedrock")).toBeInTheDocument();
  });

  it("keeps credential actions write-only and omits member model picker chrome", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <ProviderSettingsTarget />
      </ThemeWrap>,
    );
    expect(screen.getByRole("button", { name: /Replace credential/i })).toBeInTheDocument();
    expect(screen.queryByLabelText(/member model/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/runtime url/i)).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue(/sk-/i)).not.toBeInTheDocument();
  });
});
