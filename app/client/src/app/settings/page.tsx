import { AppShell } from "@/features/shell";
import { SettingsPanel } from "@/features/settings-panel/SettingsPanel";

export const dynamic = "force-dynamic";

export default function SettingsPage() {
  return (
    <AppShell>
      <SettingsPanel />
    </AppShell>
  );
}
