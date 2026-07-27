import { AppShell } from "@/features/shell";
import { ChatShell } from "@/features/chat-shell/ChatShell";

export const dynamic = "force-dynamic";

export default function ChatPage() {
  return (
    <AppShell>
      <ChatShell />
    </AppShell>
  );
}
