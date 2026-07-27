import type { components as openApiComponents } from "../api/generated/openapi.ts";
import type { components as sseComponents } from "../api/generated/sse.ts";

export type TurnStreamEvent = sseComponents["schemas"]["TurnStreamEvent"];
export type EvidenceItem = openApiComponents["schemas"]["EvidenceItemDto"];
export type AcceptedRef = openApiComponents["schemas"]["AcceptedRefDto"];
export type Citation = openApiComponents["schemas"]["CitationDto"];
export type TerminalSnapshot = openApiComponents["schemas"]["TerminalSnapshotDto"];

export type TurnTerminalStatus = "completed" | "failed" | "cancelled" | "redacted";
export type TurnRoute = "direct_llm" | "domain_rag";

export type TurnStreamProjection = {
  turnId: string | null;
  answerText: string;
  evidence: EvidenceItem[];
  stage: string | null;
  terminalStatus: TurnTerminalStatus | null;
  terminalMessage: string | null;
  acceptedRefs: AcceptedRef[];
  route: TurnRoute | null;
  citations: Citation[];
  unavailable: boolean;
};

export function createEmptyTurnProjection(): TurnStreamProjection {
  return {
    turnId: null,
    answerText: "",
    evidence: [],
    stage: null,
    terminalStatus: null,
    terminalMessage: null,
    acceptedRefs: [],
    route: null,
    citations: [],
    unavailable: false,
  };
}

function upsertEvidence(current: EvidenceItem[], items: EvidenceItem[]): EvidenceItem[] {
  const byId = new Map(current.map((item) => [item.id, item]));
  for (const item of items) byId.set(item.id, item);
  return [...byId.values()];
}

export function reduceTurnStreamEvent(
  state: TurnStreamProjection,
  event: TurnStreamEvent,
): TurnStreamProjection {
  switch (event.type) {
    case "turn.accepted":
      return {
        ...state,
        turnId: event.turnId,
        stage: "Preparing answer",
        unavailable: false,
      };
    case "route.selected":
      return {
        ...state,
        turnId: event.turnId,
        route: event.payload.route,
        stage: event.payload.route === "domain_rag" ? "Preparing grounded answer" : "Answering",
      };
    case "retrieval.started":
      return { ...state, turnId: event.turnId, stage: "Retrieving evidence" };
    case "retrieval.completed":
      return {
        ...state,
        turnId: event.turnId,
        stage: event.payload.result === "evidence_found" ? "Answering from evidence" : "No grounded context",
      };
    case "evidence.delta":
      return {
        ...state,
        turnId: event.turnId,
        evidence: upsertEvidence(state.evidence, event.payload.items),
      };
    case "answer.delta":
      return {
        ...state,
        turnId: event.turnId,
        answerText: `${state.answerText}${event.payload.text}`,
      };
    case "turn.completed":
      return {
        ...state,
        turnId: event.turnId,
        route: event.payload.route,
        acceptedRefs: [...event.payload.acceptedRefs],
        citations: [...event.payload.citations],
        terminalStatus: "completed",
        terminalMessage: null,
        stage: null,
      };
    case "turn.failed":
      return {
        ...state,
        turnId: event.turnId,
        terminalStatus: "failed",
        terminalMessage: event.payload.message,
        stage: null,
      };
    case "turn.cancelled":
      return {
        ...state,
        turnId: event.turnId,
        terminalStatus: "cancelled",
        terminalMessage: event.payload.message,
        stage: null,
      };
    case "turn.redacted":
      return {
        ...state,
        turnId: event.turnId,
        answerText: "",
        evidence: [],
        acceptedRefs: [],
        citations: [],
        terminalStatus: "redacted",
        terminalMessage: event.payload.message,
        stage: null,
      };
    default:
      return state;
  }
}

/** Replace (never merge) the turn projection from an authorized 410 terminal snapshot. */
export function replaceTurnProjectionFromTerminalSnapshot(
  snapshot: TerminalSnapshot,
): TurnStreamProjection {
  const terminalStatus: TurnTerminalStatus | null =
    snapshot.status === "running" ? null : snapshot.status;
  return {
    turnId: snapshot.turnId,
    answerText: snapshot.answer ?? "",
    evidence: [...snapshot.evidence],
    stage: null,
    terminalStatus,
    terminalMessage: null,
    acceptedRefs: [],
    route: null,
    citations: [...snapshot.citations],
    unavailable: false,
  };
}

export function createUnavailableTurnProjection(): TurnStreamProjection {
  return {
    ...createEmptyTurnProjection(),
    unavailable: true,
    terminalMessage: "History is no longer available",
  };
}
