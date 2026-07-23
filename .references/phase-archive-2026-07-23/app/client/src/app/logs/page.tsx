import { AppShell } from "@/components/layout/AppShell";
import { LogsPage as LogsObservability } from "@/features/logs-observability/LogsPage";

export const dynamic = "force-dynamic";

export default function LogsPage() {
  return (
    <AppShell>
      <LogsObservability />
    </AppShell>
  );
}
