/* Context Engine adapter for the LS chat-shell slice.
   This module is the only chat code that knows CE endpoints:

   listConversations()      GET  /api/v1/conversations
   createConversation()     POST /api/v1/conversations
   getConversation(id)      GET /api/v1/conversations/{id}
   renameConversation(id)   PATCH /api/v1/conversations/{id}
   deleteConversation(id)   DELETE /api/v1/conversations/{id}
   discoverComposerRefs()   POST /api/v1/composer-refs:discover
   streamConversationTurn() POST /api/v1/conversations/{id}/turns:stream (EVT-001 SSE)

   Abort/queue/steer/compact and Pi runtime frames are not wired: no CE contract. */

import { ceFetch } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { components } from "@/lib/api/generated/openapi";
import type { components as sseComponents } from "@/lib/api/generated/sse";
import { getSse, postSse, type SseEvent } from "@/lib/api/sse";
import { createCanonicalTurnConsumer } from "@/features/chat-shell/stream-protocol";
import { runResumableTurnStream, type StreamTransportState } from "@/features/chat-shell/stream-reconnect";

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
  status: "running" | "completed" | "failed" | "cancelled" | "redacted";
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

export type TurnStreamEvent = sseComponents["schemas"]["TurnStreamEvent"];

type TurnStreamInput = TurnStreamRequest & {
  conversationId: string;
  composerRefTokens: string[];
  onEvent: (event: TurnStreamEvent) => void;
  onTransportState?: (state: StreamTransportState) => void;
};

type TurnReplayInput = {
  conversationId: string;
  turnId: string;
  onEvent: (event: TurnStreamEvent) => void;
  after?: number;
  onTransportState?: (state: StreamTransportState) => void;
};

export type { StreamTransportState } from "@/features/chat-shell/stream-reconnect";

function streamProtocolError(message: string): ApiError {
  return new ApiError({ status: 0, code: "stream_protocol_error", message, requestId: null, fields: {} });
}

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

export async function streamConversationTurn(input: TurnStreamInput): Promise<void> {
  const consumer = createCanonicalTurnConsumer(0, input.onEvent, streamProtocolError);
  await runResumableTurnStream({
    start: () => postSse(
      `/conversations/${input.conversationId}/turns:stream`,
      {
        clientRequestId: input.clientRequestId,
        message: input.message,
        domainId: input.domainId || undefined,
        composerRefTokens: input.composerRefTokens,
      },
      consumer.receive,
    ),
    resume: (after) => getSse(
      `/conversations/${input.conversationId}/turns/${consumer.snapshot().turnId}/events?after=${after}`,
      consumer.receive,
    ),
    snapshot: consumer.snapshot,
    shouldRetry: (error) => !(error instanceof ApiError) || error.code !== "stream_protocol_error" || error.message.includes("sequence gap"),
    onState: input.onTransportState,
  });
  consumer.finish();
}

export async function streamConversationTurnEvents(input: TurnReplayInput): Promise<void> {
  const consumer = createCanonicalTurnConsumer(input.after ?? 0, input.onEvent, streamProtocolError);
  const eventsPath = (after: number) =>
    `/conversations/${input.conversationId}/turns/${input.turnId}/events?after=${after}`;
  await runResumableTurnStream({
    start: () => getSse(eventsPath(input.after ?? 0), consumer.receive),
    resume: (after) => getSse(eventsPath(after), consumer.receive),
    snapshot: consumer.snapshot,
    shouldRetry: (error) => !(error instanceof ApiError) || error.code !== "stream_protocol_error" || error.message.includes("sequence gap"),
    onState: input.onTransportState,
  });
  consumer.finish();
}

export async function cancelConversationTurn(conversationId: string, turnId: string): Promise<ChatTurn> {
  const body = await ceFetch<{ turn: ChatTurn }>(`/conversations/${conversationId}/turns/${turnId}:cancel`, {
    method: "POST",
  });
  return body.turn;
}
