"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { isApiError } from "@/lib/api/errors";
import {
  cancelConversationTurn,
  createConversation,
  getConversation,
  listConversations,
  streamConversationTurn,
  streamConversationTurnEvents,
  type AcceptedRef,
  type ChatTurn,
  type ConversationSummary,
  type TurnStreamEvent,
  type StreamTransportState,
} from "@/features/chat-shell/api";
import { listMemberDomains, type MemberDomain } from "@/features/domains/api";
import type { AssistantBlock, ChatMessage, EvidenceRow } from "@/features/chat-shell/types";
import {
  createEmptyTurnProjection,
  createUnavailableTurnProjection,
  getTerminalSnapshotFromError,
  isCursorExpiredError,
  isTerminalSnapshotDto,
  reduceTurnStreamEvent,
  replaceTurnProjectionFromTerminalSnapshot,
  type TurnStreamProjection,
} from "@/lib/stream";

type SubmittedSnapshot = {
  message: string;
  domainId: string;
  clientRequestId: string;
};

type ClientRequestPhase = "inflight" | "uncertain" | "conflict" | "accepted" | "terminal_fail";

type ClientRequestState = {
  message: string;
  domainId: string;
  id: string;
  phase: ClientRequestPhase;
};

type InspectorFence = {
  identityEpoch: number;
  conversationId: string | null;
  selectedTurnId: string | null;
  generation: number;
};

function requestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `turn-${crypto.randomUUID()}`;
  }
  return `turn-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function formatErrorMessage(error: unknown): string {
  if (!isApiError(error)) return "Request failed.";
  const base = error.message || "Request failed.";
  return error.requestId ? `${base} (request ${error.requestId})` : base;
}

function isAuthExpiryError(error: unknown): boolean {
  if (!isApiError(error)) return false;
  return (
    error.code === "session_expired" ||
    error.code === "unauthenticated" ||
    error.status === 401
  );
}

function isUncertainPreAcceptError(error: unknown): boolean {
  if (!isApiError(error)) return true;
  if (
    error.code === "domain_required" ||
    error.code === "domain_not_query_eligible" ||
    error.code === "idempotency_conflict" ||
    error.code === "validation_error" ||
    error.code === "csrf_invalid" ||
    isAuthExpiryError(error) ||
    isCursorExpiredError(error)
  ) {
    return false;
  }
  return error.status === 0 || error.status === 408 || error.status === 429 || error.status >= 500;
}

function stageFromProjection(projection: TurnStreamProjection): string | null {
  return projection.stage;
}

function turnToMessages(turn: ChatTurn): ChatMessage[] {
  /* Evidence rows are not timeline blocks; the Evidence Panel renders them. */
  const blocks: AssistantBlock[] = [];
  if (turn.assistantAnswer) {
    blocks.push({ kind: "text", id: `${turn.id}-text`, text: turn.assistantAnswer });
  }
  if (turn.error?.message) {
    blocks.push({ kind: "error", id: `${turn.id}-error`, text: turn.error.message });
  }
  return [
    {
      id: `${turn.id}-user`,
      role: "user",
      turnId: turn.id,
      text: turn.userMessage,
      acceptedRefs: turn.acceptedRefs,
    },
    {
      id: `${turn.id}-assistant`,
      role: "assistant",
      turnId: turn.id,
      text: turn.assistantAnswer ?? "",
      blocks,
      status: turn.status,
      route: turn.route,
      evidenceCount: turn.evidence.length,
    },
  ];
}

export function useChatShell() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversation, setConversation] = useState<ConversationSummary | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [domains, setDomains] = useState<MemberDomain[]>([]);
  const [input, setInput] = useState("");
  const [domainId, setDomainId] = useState("");
  const [streamText, setStreamText] = useState("");
  const [streamStage, setStreamStage] = useState<string | null>(null);
  const [streamEvidence, setStreamEvidence] = useState<EvidenceRow[]>([]);
  const [streamingTurnId, setStreamingTurnId] = useState<string | null>(null);
  const [replayingTurnId, setReplayingTurnId] = useState<string | null>(null);
  /* Evidence Panel: turn-scoped view state. selectedTurnId null = follow the
     live/latest turn; panel auto-opens when the active turn yields evidence. */
  const [panelOpen, setPanelOpen] = useState(false);
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [pendingRefs, setPendingRefs] = useState<AcceptedRef[]>([]);
  const [submittedSnapshot, setSubmittedSnapshot] = useState<SubmittedSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamTransportState, setStreamTransportState] = useState<StreamTransportState>("connected");
  const [error, setError] = useState<string | null>(null);

  const projectionRef = useRef<TurnStreamProjection>(createEmptyTurnProjection());
  const streamOwnerConversationIdRef = useRef<string | null>(null);
  const clientRequestRef = useRef<ClientRequestState | null>(null);
  const submittedSnapshotRef = useRef<SubmittedSnapshot | null>(null);
  const inspectorFenceRef = useRef<InspectorFence>({
    identityEpoch: 0,
    conversationId: null,
    selectedTurnId: null,
    generation: 0,
  });
  const identityEpochRef = useRef(0);

  const bumpInspectorFence = useCallback(
    (nextConversationId: string | null, nextSelectedTurnId: string | null) => {
      const generation = inspectorFenceRef.current.generation + 1;
      inspectorFenceRef.current = {
        identityEpoch: identityEpochRef.current,
        conversationId: nextConversationId,
        selectedTurnId: nextSelectedTurnId,
        generation,
      };
      return generation;
    },
    [],
  );

  const isInspectorFenceCurrent = useCallback(
    (conversationId: string | null, turnId: string | null, generation: number) => {
      const fence = inspectorFenceRef.current;
      return (
        fence.generation === generation &&
        fence.identityEpoch === identityEpochRef.current &&
        fence.conversationId === conversationId &&
        fence.selectedTurnId === turnId
      );
    },
    [],
  );

  const viewConversationIdRef = useRef<string | null>(null);

  const clearPrivateView = useCallback(() => {
    identityEpochRef.current += 1;
    bumpInspectorFence(null, null);
    streamOwnerConversationIdRef.current = null;
    viewConversationIdRef.current = null;
    clientRequestRef.current = null;
    projectionRef.current = createEmptyTurnProjection();
    setConversations([]);
    setConversation(null);
    setTurns([]);
    setInput("");
    setDomainId("");
    setStreamText("");
    setStreamStage(null);
    setStreamEvidence([]);
    setStreamingTurnId(null);
    setReplayingTurnId(null);
    setPanelOpen(false);
    setSelectedTurnId(null);
    setSelectedEvidenceId(null);
    setPendingMessage(null);
    setPendingRefs([]);
    submittedSnapshotRef.current = null;
    setSubmittedSnapshot(null);
    setStreaming(false);
    setStreamTransportState("connected");
    setError(null);
  }, [bumpInspectorFence]);

  const projectStreamState = useCallback(
    (projection: TurnStreamProjection, event: TurnStreamEvent | null) => {
      const ownerId = streamOwnerConversationIdRef.current;
      /* Drop projection updates when the user is viewing another conversation. */
      if (ownerId === null || ownerId !== viewConversationIdRef.current) return;
      const fenceGen = inspectorFenceRef.current.generation;
      const fenceTurnId = inspectorFenceRef.current.selectedTurnId;

      setStreamingTurnId(projection.turnId);
      setStreamText(projection.answerText);
      setStreamStage(stageFromProjection(projection));
      setStreamEvidence(projection.evidence);
      setPendingRefs(projection.acceptedRefs);

      if (event?.type === "turn.accepted") {
        const submitted = submittedSnapshotRef.current;
        if (submitted) {
          setInput((draft) => (draft.trim() === submitted.message ? "" : draft));
        }
        submittedSnapshotRef.current = null;
        setSubmittedSnapshot(null);
        if (clientRequestRef.current) {
          clientRequestRef.current = { ...clientRequestRef.current, phase: "accepted" };
        }
      }

      if (projection.evidence.length > 0) {
        const conversationId = ownerId;
        if (isInspectorFenceCurrent(conversationId, fenceTurnId, fenceGen) || fenceTurnId === null) {
          setPanelOpen(true);
        }
      }

      if (projection.terminalStatus === "failed" || projection.terminalStatus === "cancelled") {
        if (projection.terminalMessage) setError(projection.terminalMessage);
        if (clientRequestRef.current?.phase === "inflight") {
          clientRequestRef.current = { ...clientRequestRef.current, phase: "terminal_fail" };
        }
      }

      if (projection.terminalStatus === "redacted") {
        setStreamText("");
        setStreamEvidence([]);
        setPendingRefs([]);
        setStreamingTurnId(null);
        if (isInspectorFenceCurrent(ownerId, fenceTurnId, fenceGen) || fenceTurnId === null) {
          setPanelOpen(false);
          setSelectedEvidenceId(null);
        }
      }

      if (projection.unavailable && projection.terminalMessage) {
        setError(projection.terminalMessage);
      }
    },
    [isInspectorFenceCurrent],
  );

  const handleStreamEvent = useCallback(
    (event: TurnStreamEvent) => {
      const ownerId = streamOwnerConversationIdRef.current;
      if (ownerId === null || ownerId !== viewConversationIdRef.current) return;
      const next = reduceTurnStreamEvent(projectionRef.current, event);
      projectionRef.current = next;
      projectStreamState(next, event);
    },
    [projectStreamState],
  );

  useEffect(() => {
    let cancelled = false;
    void listConversations()
      .then((rows) => {
        if (!cancelled) setConversations(rows);
      })
      .catch((err) => {
        if (cancelled) return;
        if (isAuthExpiryError(err)) {
          clearPrivateView();
          setError(formatErrorMessage(err));
          return;
        }
      });
    void listMemberDomains()
      .then((rows) => {
        if (!cancelled) setDomains(rows);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [clearPrivateView]);

  const loadConversation = useCallback(
    async (conversationId: string, options?: { turnId?: string | null }) => {
      setLoading(true);
      setError(null);
      setStreamingTurnId(null);
      setReplayingTurnId(null);
      const restoreTurnId = options?.turnId?.trim() || null;
      const fenceGen = bumpInspectorFence(conversationId, restoreTurnId);
      try {
        const detail = await getConversation(conversationId);
        if (!isInspectorFenceCurrent(conversationId, restoreTurnId, fenceGen)) return;
        viewConversationIdRef.current = detail.conversation.id;
        setConversation(detail.conversation);
        setTurns(detail.turns);
        setSelectedEvidenceId(null);
        const restoreTurn = restoreTurnId ? detail.turns.find((row) => row.id === restoreTurnId) : null;
        if (restoreTurn) {
          setSelectedTurnId(restoreTurn.id);
          bumpInspectorFence(conversationId, restoreTurn.id);
          setPanelOpen(restoreTurn.evidence.length > 0);
        } else {
          setSelectedTurnId(null);
          bumpInspectorFence(conversationId, null);
          const lastTurn = detail.turns[detail.turns.length - 1];
          setPanelOpen((lastTurn?.evidence.length ?? 0) > 0);
        }
      } catch (err) {
        if (!isInspectorFenceCurrent(conversationId, restoreTurnId, fenceGen)) return;
        if (isAuthExpiryError(err)) {
          clearPrivateView();
          setError(formatErrorMessage(err));
          return;
        }
        setError(formatErrorMessage(err));
      } finally {
        setLoading(false);
      }
    },
    [bumpInspectorFence, clearPrivateView, isInspectorFenceCurrent],
  );

  const applyCursorExpiredRecovery = useCallback(
    async (err: unknown, conversationId: string, turnId?: string | null) => {
      const rawSnapshot = getTerminalSnapshotFromError(err);
      if (isTerminalSnapshotDto(rawSnapshot)) {
        const projection = replaceTurnProjectionFromTerminalSnapshot(rawSnapshot);
        projectionRef.current = projection;
        projectStreamState(projection, null);
        await loadConversation(conversationId, { turnId: projection.turnId ?? turnId });
        return;
      }

      const fenceGen = bumpInspectorFence(conversationId, turnId ?? null);
      try {
        const detail = await getConversation(conversationId);
        if (!isInspectorFenceCurrent(conversationId, turnId ?? null, fenceGen)) return;
        setConversation(detail.conversation);
        setTurns(detail.turns);
        const restored = turnId ? detail.turns.find((row) => row.id === turnId) : null;
        if (restored) {
          setSelectedTurnId(restored.id);
          setPanelOpen(restored.evidence.length > 0);
          setError(null);
          return;
        }
        if (detail.turns.length > 0) {
          setError(null);
          return;
        }
        const unavailable = createUnavailableTurnProjection();
        projectionRef.current = unavailable;
        projectStreamState(unavailable, null);
      } catch (reloadError) {
        if (!isInspectorFenceCurrent(conversationId, turnId ?? null, fenceGen)) return;
        if (isAuthExpiryError(reloadError)) {
          clearPrivateView();
          setError(formatErrorMessage(reloadError));
          return;
        }
        const unavailable = createUnavailableTurnProjection();
        projectionRef.current = unavailable;
        projectStreamState(unavailable, null);
      }
    },
    [bumpInspectorFence, clearPrivateView, isInspectorFenceCurrent, loadConversation, projectStreamState],
  );

  const startConversation = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const created = await createConversation("Chat");
      bumpInspectorFence(created.id, null);
      viewConversationIdRef.current = created.id;
      setConversation(created);
      setConversations((current) => [created, ...current]);
      setTurns([]);
      setStreamText("");
      setStreamEvidence([]);
      setPanelOpen(false);
      setStreamingTurnId(null);
      setReplayingTurnId(null);
      setSelectedTurnId(null);
      setSelectedEvidenceId(null);
      setPendingMessage(null);
      setPendingRefs([]);
      submittedSnapshotRef.current = null;
      setSubmittedSnapshot(null);
      return created.id;
    } catch (err) {
      if (isAuthExpiryError(err)) {
        clearPrivateView();
        setError(formatErrorMessage(err));
        return null;
      }
      setError(formatErrorMessage(err));
      return null;
    } finally {
      setLoading(false);
    }
  }, [bumpInspectorFence, clearPrivateView]);

  const updateInput = useCallback((value: string) => {
    setInput(value);
  }, []);

  const resolveClientRequestId = useCallback((message: string, nextDomainId: string): string => {
    const prev = clientRequestRef.current;
    const sameEffective =
      prev !== null && prev.message === message && prev.domainId === nextDomainId;
    if (sameEffective && prev.phase === "uncertain") {
      clientRequestRef.current = { ...prev, phase: "inflight" };
      return prev.id;
    }
    const id = requestId();
    clientRequestRef.current = {
      message,
      domainId: nextDomainId,
      id,
      phase: "inflight",
    };
    return id;
  }, []);

  const submit = useCallback(
    async (messageOverride?: string) => {
      const message = (messageOverride ?? input).trim();
      if (!message || streaming) return;
      let conversationId = conversation?.id ?? null;
      if (!conversationId) conversationId = await startConversation();
      if (!conversationId) return;

      const effectiveDomainId = domainId.trim();
      const clientRequestId = resolveClientRequestId(message, effectiveDomainId);

      setStreaming(true);
      setStreamTransportState("connected");
      setStreamingTurnId(null);
      setError(null);
      projectionRef.current = createEmptyTurnProjection();
      streamOwnerConversationIdRef.current = conversationId;
      viewConversationIdRef.current = conversationId;
      setStreamText("");
      setStreamStage(null);
      setStreamEvidence([]);
      setPendingRefs([]);
      setPendingMessage(message);
      const snapshot = { message, domainId: effectiveDomainId, clientRequestId };
      submittedSnapshotRef.current = snapshot;
      setSubmittedSnapshot(snapshot);
      /* New turn: the panel follows the in-flight turn again. */
      setSelectedTurnId(null);
      setSelectedEvidenceId(null);
      bumpInspectorFence(conversationId, null);

      let keepPendingBubble = false;
      try {
        await streamConversationTurn({
          conversationId,
          clientRequestId,
          message,
          domainId: effectiveDomainId || undefined,
          composerRefTokens: [],
          onEvent: handleStreamEvent,
          onTransportState: setStreamTransportState,
        });
        if (
          streamOwnerConversationIdRef.current === conversationId &&
          viewConversationIdRef.current === conversationId
        ) {
          await loadConversation(conversationId);
        }
      } catch (err) {
        if (streamOwnerConversationIdRef.current !== conversationId) return;

        if (isCursorExpiredError(err)) {
          await applyCursorExpiredRecovery(err, conversationId, projectionRef.current.turnId);
          return;
        }

        if (isAuthExpiryError(err)) {
          clearPrivateView();
          setError(formatErrorMessage(err));
          setStreamingTurnId(null);
          return;
        }

        if (isApiError(err) && err.code === "idempotency_conflict") {
          if (clientRequestRef.current) {
            clientRequestRef.current = { ...clientRequestRef.current, phase: "conflict" };
          }
          setError(formatErrorMessage(err));
          setStreamingTurnId(null);
          return;
        }

        if (
          isApiError(err) &&
          (err.code === "domain_required" || err.code === "domain_not_query_eligible")
        ) {
          if (clientRequestRef.current) {
            clientRequestRef.current = { ...clientRequestRef.current, phase: "terminal_fail" };
          }
          setError(formatErrorMessage(err));
          setStreamingTurnId(null);
          return;
        }

        if (isUncertainPreAcceptError(err) && !projectionRef.current.turnId) {
          if (clientRequestRef.current) {
            clientRequestRef.current = { ...clientRequestRef.current, phase: "uncertain" };
          }
          setError(formatErrorMessage(err));
          keepPendingBubble = true;
          setStreamingTurnId(null);
          return;
        }

        /* Accepted or otherwise attached: reload durable turn; Retry resumes GET. */
        if (projectionRef.current.turnId) {
          if (clientRequestRef.current) {
            clientRequestRef.current = { ...clientRequestRef.current, phase: "accepted" };
          }
          setError(formatErrorMessage(err));
          if (viewConversationIdRef.current === conversationId) {
            await loadConversation(conversationId, { turnId: projectionRef.current.turnId });
          }
          setStreamingTurnId(null);
          return;
        }

        if (clientRequestRef.current) {
          clientRequestRef.current = { ...clientRequestRef.current, phase: "terminal_fail" };
        }
        setError(formatErrorMessage(err));
        setStreamingTurnId(null);
      } finally {
        /* Only clear this submit's presentation if we still own the stream slot. */
        if (streamOwnerConversationIdRef.current === conversationId) {
          setStreaming(false);
          setStreamStage(null);
          if (!keepPendingBubble) setPendingMessage(null);
        }
      }
    },
    [
      applyCursorExpiredRecovery,
      bumpInspectorFence,
      clearPrivateView,
      conversation,
      domainId,
      handleStreamEvent,
      input,
      loadConversation,
      resolveClientRequestId,
      startConversation,
      streaming,
    ],
  );

  const clearError = useCallback(() => setError(null), []);

  const runningCancellableTurnId = useMemo(() => {
    if (streamingTurnId) return streamingTurnId;
    if (selectedTurnId) {
      const selected = turns.find((row) => row.id === selectedTurnId);
      if (selected?.status === "running") return selected.id;
    }
    const running = turns.find((row) => row.status === "running");
    return running?.id ?? null;
  }, [selectedTurnId, streamingTurnId, turns]);

  const selectedReplayableTurnId = useMemo(() => {
    if (!selectedTurnId) return null;
    if (runningCancellableTurnId === selectedTurnId) return null;
    const selected = turns.find((row) => row.id === selectedTurnId);
    if (!selected) return null;
    return selected.status === "running" ? null : selected.id;
  }, [runningCancellableTurnId, selectedTurnId, turns]);

  const cancelTurn = useCallback(async () => {
    const turnId = runningCancellableTurnId;
    if (!conversation || !turnId) return;

    setError(null);
    try {
      await cancelConversationTurn(conversation.id, turnId);
      await loadConversation(conversation.id, { turnId });
      setStreamingTurnId(null);
    } catch (err) {
      if (isAuthExpiryError(err)) {
        clearPrivateView();
        setError(formatErrorMessage(err));
        return;
      }
      setError(formatErrorMessage(err));
    }
  }, [clearPrivateView, conversation, loadConversation, runningCancellableTurnId]);

  const replayTurn = useCallback(async () => {
    const turnId = selectedReplayableTurnId;
    if (!conversation || !turnId) return;

    setError(null);
    setReplayingTurnId(turnId);
    streamOwnerConversationIdRef.current = conversation.id;
    viewConversationIdRef.current = conversation.id;
    projectionRef.current = createEmptyTurnProjection();
    try {
      await streamConversationTurnEvents({
        conversationId: conversation.id,
        turnId,
        onEvent: handleStreamEvent,
      });
      await loadConversation(conversation.id, { turnId });
    } catch (err) {
      if (isCursorExpiredError(err)) {
        await applyCursorExpiredRecovery(err, conversation.id, turnId);
        return;
      }
      if (isAuthExpiryError(err)) {
        clearPrivateView();
        setError(formatErrorMessage(err));
        return;
      }
      setError(formatErrorMessage(err));
    } finally {
      setReplayingTurnId(null);
    }
  }, [
    applyCursorExpiredRecovery,
    clearPrivateView,
    conversation,
    handleStreamEvent,
    loadConversation,
    selectedReplayableTurnId,
  ]);

  /* Evidence Panel selection: click an assistant message to bind the panel to
     that turn; a turn with evidence opens the panel. */
  const selectTurn = useCallback(
    (turnId: string | null) => {
      setSelectedTurnId(turnId);
      setSelectedEvidenceId(null);
      bumpInspectorFence(conversation?.id ?? null, turnId);
      if (turnId === null) return;
      const turn = turns.find((row) => row.id === turnId);
      if ((turn?.evidence.length ?? 0) > 0) setPanelOpen(true);
    },
    [bumpInspectorFence, conversation?.id, turns],
  );

  const selectEvidence = useCallback((evidenceId: string) => {
    setSelectedEvidenceId(evidenceId);
  }, []);

  /* Panel rows: selected turn's evidence, else the in-flight stream, else the
     latest persisted turn. Direct LLM turns have no evidence event, so the
     panel stays empty (and closed) for them. */
  const panelEvidence = useMemo<EvidenceRow[]>(() => {
    if (selectedTurnId) {
      return turns.find((row) => row.id === selectedTurnId)?.evidence ?? [];
    }
    if (pendingMessage !== null) return streamEvidence;
    return turns[turns.length - 1]?.evidence ?? [];
  }, [pendingMessage, selectedTurnId, streamEvidence, turns]);

  const panelAcceptedRefs = useMemo<AcceptedRef[]>(() => {
    if (selectedTurnId) {
      return turns.find((row) => row.id === selectedTurnId)?.acceptedRefs ?? [];
    }
    if (pendingMessage !== null) return pendingRefs;
    return turns[turns.length - 1]?.acceptedRefs ?? [];
  }, [pendingMessage, pendingRefs, selectedTurnId, turns]);

  /* Timeline projection: persisted turns plus the live streaming turn.
     Evidence is not projected into blocks; the Evidence Panel renders it. */
  const messages = useMemo<ChatMessage[]>(() => {
    const rows = turns.flatMap(turnToMessages);
    if (pendingMessage !== null) {
      rows.push({
        id: "pending-user",
        role: "user",
        turnId: null,
        text: pendingMessage,
        acceptedRefs: pendingRefs,
      });
      const blocks: AssistantBlock[] = [];
      if (streamStage) blocks.push({ kind: "event", id: "pending-stage", text: streamStage });
      if (streamText) blocks.push({ kind: "text", id: "pending-text", text: streamText });
      rows.push({
        id: "pending-assistant",
        role: "assistant",
        turnId: null,
        text: streamText,
        blocks,
        status: "running",
        evidenceCount: streamEvidence.length,
      });
    }
    return rows;
  }, [pendingMessage, pendingRefs, streamEvidence, streamStage, streamText, turns]);

  const lastUserMessage = useMemo(
    () => [...messages].reverse().find((message) => message.role === "user")?.text ?? "",
    [messages],
  );

  const retryLast = useCallback(async () => {
    const conversationId = conversation?.id ?? streamOwnerConversationIdRef.current;
    const turnId = projectionRef.current.turnId;
    const phase = clientRequestRef.current?.phase;
    if (conversationId && turnId && (phase === "accepted" || phase === "inflight")) {
      setError(null);
      setStreaming(true);
      setStreamTransportState("connected");
      streamOwnerConversationIdRef.current = conversationId;
      viewConversationIdRef.current = conversationId;
      try {
        await streamConversationTurnEvents({
          conversationId,
          turnId,
          onEvent: handleStreamEvent,
          onTransportState: setStreamTransportState,
        });
        if (
          streamOwnerConversationIdRef.current === conversationId &&
          viewConversationIdRef.current === conversationId
        ) {
          await loadConversation(conversationId, { turnId });
        }
      } catch (err) {
        if (streamOwnerConversationIdRef.current !== conversationId) return;
        if (isCursorExpiredError(err)) {
          await applyCursorExpiredRecovery(err, conversationId, turnId);
          return;
        }
        if (isAuthExpiryError(err)) {
          clearPrivateView();
          setError(formatErrorMessage(err));
          return;
        }
        setError(formatErrorMessage(err));
      } finally {
        if (streamOwnerConversationIdRef.current === conversationId) {
          setStreaming(false);
          setStreamStage(null);
          setStreamingTurnId(null);
        }
      }
      return;
    }
    const message = lastUserMessage || input;
    if (message.trim()) await submit(message);
  }, [
    applyCursorExpiredRecovery,
    clearPrivateView,
    conversation,
    handleStreamEvent,
    input,
    lastUserMessage,
    loadConversation,
    submit,
  ]);

  return {
    conversations,
    conversation,
    domains,
    messages,
    turns,
    input,
    domainId,
    streaming,
    streamStage,
    streamTransportState,
    loading,
    error,
    lastUserMessage,
    panelOpen,
    panelEvidence,
    panelAcceptedRefs,
    selectedTurnId,
    selectedEvidenceId,
    streamingTurnId,
    runningCancellableTurnId,
    selectedReplayableTurnId,
    replayingTurnId,
    submittedSnapshot,
    setPanelOpen,
    selectTurn,
    selectEvidence,
    setDomainId,
    updateInput,
    loadConversation,
    startConversation,
    submit,
    retryLast,
    cancelTurn,
    replayTurn,
    clearError,
  };
}
