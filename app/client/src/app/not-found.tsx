import { AppShell } from "@/features/shell";
import { PageState } from "@/components/ui/PageState";

export default function NotFoundPage() {
  return (
    <AppShell>
      <PageState title="Not found" message="This surface is not available." />
    </AppShell>
  );
}
