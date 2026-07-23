import { AppShell } from "@/components/layout/AppShell";
import { GraphPage } from "@/features/graph/GraphPage";

export const dynamic = "force-dynamic";

export default function DatabaseVisualizePage() {
  return (
    <AppShell>
      <GraphPage />
    </AppShell>
  );
}
