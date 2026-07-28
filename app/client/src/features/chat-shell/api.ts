/* Context Engine adapter for the chat-shell slice.
   Thin wrappers over generated OpenAPI/SSE component types.

   listConversations()      GET  /api/v1/conversations
   createConversation()     POST /api/v1/conversations
   getConversation(id)      GET /api/v1/conversations/{id}
   renameConversation(id)   PATCH /api/v1/conversations/{id}
   deleteConversation(id)   DELETE /api/v1/conversations/{id}
   discoverComposerRefs()   POST /api/v1/composer-refs:discover (source/template; Evidence attach deferred)
   streamConversationTurn() POST /api/v1/conversations/{id}/turns:stream
*/

import { ceFetch, ifMatchHeader } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { components } from "@/lib/api/generated/openapi";
import type { components as sseComponents } from "@/lib/api/generated/sse";
import { getSse, postSse } from "@/lib/api/sse";
import {
  createCanonicalTurnConsumer,
  runResumableTurnStream,
  type StreamTransportState,
} from "@/lib/stream";

type ComposerRefDiscoverRequest = components["schemas"]["ComposerRefDiscoverRequest"];
type ConversationTitleRequest = components["schemas"]["ConversationTitleRequest"];
type TurnStreamRequest = components["schemas"]["TurnStreamRequest"];

export type ComposerRefKind = NonNullable<ComposerRefDiscoverRequest["kinds"]>[number];
export type AcceptedRef = components["schemas"]["AcceptedRefDto"];
export type ChatTurn = components["schemas"]["TurnDto"];
export type ConversationSummary = components["schemas"]["ConversationSummaryDto"];
export type ConversationDetail = components["schemas"]["ConversationDetailResponseDto"];
export type EvidenceItem = components["schemas"]["EvidenceItemDto"];
export type TurnStreamEvent = sseComponents["schemas"]["TurnStreamEvent"];

export type ComposerRef = components["schemas"]["ComposerRefDto"];

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

export type { StreamTransportState } from "@/lib/stream";

function streamProtocolError(message: string): ApiError {
  return new ApiError({ status: 0, code: "stream_protocol_error", message, requestId: null, fields: {} });
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const body = await ceFetch<components["schemas"]["ConversationListResponse"]>("/conversations");
  return body.conversations;
}

export async function createConversation(title: string | null = null): Promise<ConversationSummary> {
  const payload: ConversationTitleRequest = { title };
  const body = await ceFetch<components["schemas"]["ConversationMutationResponse"]>("/conversations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return body.conversation;
}

export async function getConversation(conversationId: string): Promise<ConversationDetail> {
  return ceFetch<ConversationDetail>(`/conversations/${conversationId}`);
}

export async function renameConversation(
  conversationId: string,
  title: string,
  version: number,
): Promise<ConversationSummary> {
  const headers = ifMatchHeader(version);
  if (!headers) {
    throw new Error("Conversation version is required for rename (If-Match).");
  }
  const payload: ConversationTitleRequest = { title };
  const body = await ceFetch<components["schemas"]["ConversationMutationResponse"]>(
    `/conversations/${conversationId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
      headers,
    },
  );
  return body.conversation;
}

export async function deleteConversation(conversationId: string, version: number): Promise<void> {
  const headers = ifMatchHeader(version);
  if (!headers) {
    throw new Error("Conversation version is required for delete (If-Match).");
  }
  await ceFetch<void>(`/conversations/${conversationId}`, { method: "DELETE", headers });
}

/** Discover governed composer refs. Callers must request only contracted kinds; Evidence attach stays deferred (P11-04). */
export async function discoverComposerRefs(input: ComposerRefDiscoverRequest): Promise<ComposerRef[]> {
  const body = await ceFetch<components["schemas"]["ComposerRefDiscoverResponse"]>("/composer-refs:discover", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return body.refs;
}

export async function streamConversationTurn(input: TurnStreamInput): Promise<void> {
  const consumer = createCanonicalTurnConsumer(0, input.onEvent, streamProtocolError);
  await runResumableTurnStream({
    start: () =>
      postSse(
        `/conversations/${input.conversationId}/turns:stream`,
        {
          clientRequestId: input.clientRequestId,
          message: input.message,
          domainId: input.domainId || undefined,
          composerRefTokens: input.composerRefTokens,
        },
        consumer.receive,
      ),
    resume: (after) =>
      getSse(
        `/conversations/${input.conversationId}/turns/${consumer.snapshot().turnId}/events?after=${after}`,
        consumer.receive,
      ),
    snapshot: consumer.snapshot,
    shouldRetry: (error) => {
      if (!(error instanceof ApiError)) return true;
      if (error.status === 410 || error.code === "cursor_expired") return false;
      if (error.code === "stream_protocol_error") return error.message.includes("sequence gap");
      return true;
    },
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
    shouldRetry: (error) => {
      if (!(error instanceof ApiError)) return true;
      if (error.status === 410 || error.code === "cursor_expired") return false;
      if (error.code === "stream_protocol_error") return error.message.includes("sequence gap");
      return true;
    },
    onState: input.onTransportState,
  });
  consumer.finish();
}

export async function cancelConversationTurn(conversationId: string, turnId: string): Promise<ChatTurn> {
  const body = await ceFetch<components["schemas"]["TurnMutationResponse"]>(
    `/conversations/${conversationId}/turns/${turnId}:cancel`,
    {
      method: "POST",
    },
  );
  return body.turn;
}
