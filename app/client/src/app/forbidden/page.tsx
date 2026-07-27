import { AppShell } from "@/features/shell";
import { PageState } from "@/components/ui/PageState";

export default function ForbiddenPage() {
  return (
    <AppShell>
      <PageState title="Forbidden" message="You do not have access to this surface." tone="danger" />
    </AppShell>
  );
}
