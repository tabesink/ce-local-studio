import { AppShell } from "@/components/layout/AppShell";
import { ChatShell } from "@/features/chat-shell/ChatShell";

export const dynamic = "force-dynamic";

export default function ChatPage() {
  return (
    <AppShell>
      <ChatShell />
    </AppShell>
  );
}
