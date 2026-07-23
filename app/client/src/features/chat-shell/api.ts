/* Context Engine adapter for the LS chat-shell slice.
   This module is the only chat code that knows CE endpoints:

   listConversations()      GET  /api/v1/conversations
   createConversation()     POST /api/v1/conversations
   getConversation(id)      GET  /api/v1/conversations/{id}
   renameConversation(id)   PATCH /api/v1/conversations/{id}
   deleteConversation(id)   DELETE /api/v1/conversations/{id}
   discoverComposerRefs()   POST /api/v1/composer-refs:discover
   streamConversationTurn() POST /api/v1/conversations/{id}/turns:stream (EVT-001 SSE)

   Abort/queue/steer/compact and Pi runtime frames are not wired: no CE contract. */

import { ceFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/openapi";
import { postSse, type SseEvent } from "@/lib/api/sse";

type ComposerRefDiscoverRequest = components["schemas"]["ComposerRefDiscoverRequest"];
type ConversationTitleRequest = components["schemas"]["ConversationTitleRequest"];
type TurnStreamRequest = components["schemas"]["TurnStreamRequest"];

export type ComposerRefKind = NonNullable<ComposerRefDiscoverRequest["kinds"]>[number];

export type ComposerRef = {
  refToken: string;
  kind: ComposerRefKind;
  label: string;
  description?: string | null;
  disabledReason?: string | null;
};

export type AcceptedRef = {
  id: string;
  kind: ComposerRefKind;
  order: number;
  label: string | null;
  description: string | null;
};

export type ChatTurn = {
  id: string;
  clientRequestId: string;
  domainId: string | null;
  route: "direct_llm" | "domain_rag";
  status: "running" | "completed" | "failed" | "redacted";
  stopReason: string | null;
  userMessage: string;
  assistantAnswer: string | null;
  safeError: { code: string | null; message: string | null } | null;
  acceptedRefs: AcceptedRef[];
  evidence: Array<{ id: string; citationLabel: string | null; sourceLabel: string | null; excerpt: string | null }>;
  citations: Array<{ evidenceRefId: string; citationLabel: string | null }>;
  budget: {
    planStepCount: number;
    retrievalOperationCount: number;
    repairAttemptCount: number;
  };
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  updatedAt: string;
};

export type ConversationSummary = {
  id: string;
  title: string | null;
  createdAt: string;
  updatedAt: string;
};

export type ConversationDetail = {
  conversation: ConversationSummary;
  turns: ChatTurn[];
};

export type TurnStreamEvent =
  | { event: "stage"; payload: { turnId: string; stage: string } }
  | { event: "token"; payload: { turnId: string; text: string } }
  | { event: "evidence"; payload: { turnId: string; evidence: ChatTurn["evidence"] } }
  | {
      event: "done";
      payload: {
        turnId: string;
        route: ChatTurn["route"];
        status: ChatTurn["status"];
        stopReason: string | null;
        citations: ChatTurn["citations"];
        acceptedRefs: AcceptedRef[];
        budget: ChatTurn["budget"];
        replay: boolean;
      };
    }
  | { event: "error"; payload: { turnId: string; code: string; message: string; replay: boolean } };

export async function listConversations(): Promise<ConversationSummary[]> {
  const body = await ceFetch<{ conversations: ConversationSummary[] }>("/conversations");
  return body.conversations;
}

export async function createConversation(title: string | null = null): Promise<ConversationSummary> {
  const payload: ConversationTitleRequest = { title };
  const body = await ceFetch<{ conversation: ConversationSummary }>("/conversations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return body.conversation;
}

export async function getConversation(conversationId: string): Promise<ConversationDetail> {
  return ceFetch<ConversationDetail>(`/conversations/${conversationId}`);
}

export async function renameConversation(conversationId: string, title: string): Promise<ConversationSummary> {
  const payload: ConversationTitleRequest = { title };
  const body = await ceFetch<{ conversation: ConversationSummary }>(`/conversations/${conversationId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return body.conversation;
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await ceFetch<void>(`/conversations/${conversationId}`, { method: "DELETE" });
}

export async function discoverComposerRefs(input: ComposerRefDiscoverRequest): Promise<ComposerRef[]> {
  const body = await ceFetch<{ refs: ComposerRef[] }>("/composer-refs:discover", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return body.refs;
}

type TurnStreamInput = TurnStreamRequest & {
  conversationId: string;
  composerRefTokens: string[];
  onEvent: (event: TurnStreamEvent) => void;
};

export async function streamConversationTurn(input: TurnStreamInput): Promise<void> {
  await postSse(
    `/conversations/${input.conversationId}/turns:stream`,
    {
      clientRequestId: input.clientRequestId,
      message: input.message,
      domainId: input.domainId || undefined,
      composerRefTokens: input.composerRefTokens,
    },
    (event: SseEvent) => input.onEvent(event as TurnStreamEvent),
  );
}
