import { AppShell } from "@/components/layout/AppShell";
import { SettingsPanel } from "@/features/settings-panel/SettingsPanel";

export const dynamic = "force-dynamic";

export default function SettingsPage() {
  return (
    <AppShell>
      <SettingsPanel />
    </AppShell>
  );
}
