/* LS chat-shell timeline model adapted to Context Engine turns.
   Pi tool/thinking blocks are not produced: CE EVT-001 has no such events. */

import type { AcceptedRef, ChatTurn, EvidenceItem } from "@/features/chat-shell/api";

export type EvidenceRow = EvidenceItem;

/* Evidence is not a timeline block: the turn-scoped Evidence Panel owns
   Evidence display (F-009 context-panel-tabs v1). */
export type AssistantBlock =
  | { kind: "text"; id: string; text: string }
  | { kind: "event"; id: string; text: string }
  | { kind: "error"; id: string; text: string };

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  turnId: string | null;
  text: string;
  acceptedRefs?: AcceptedRef[];
  blocks?: AssistantBlock[];
  status?: ChatTurn["status"];
  route?: ChatTurn["route"];
  evidenceCount?: number;
};
