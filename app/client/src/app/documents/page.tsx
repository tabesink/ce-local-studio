import { AppShell } from "@/components/layout/AppShell";
import { DocumentsPage as DocumentsLibrary } from "@/features/documents/DocumentsPage";

export const dynamic = "force-dynamic";

export default function DocumentsPage() {
  return (
    <AppShell>
      <DocumentsLibrary />
    </AppShell>
  );
}
