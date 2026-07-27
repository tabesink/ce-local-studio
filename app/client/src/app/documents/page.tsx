import { AppShell } from "@/features/shell";
import { DocumentsPage as DocumentsLibrary } from "@/features/documents/DocumentsPage";

export const dynamic = "force-dynamic";

export default function DocumentsPage() {
  return (
    <AppShell>
      <DocumentsLibrary />
    </AppShell>
  );
}
