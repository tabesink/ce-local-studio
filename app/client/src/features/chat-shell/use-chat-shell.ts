"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { isApiError } from "@/lib/api/errors";
import {
  cancelConversationTurn,
  createConversation,
  discoverComposerRefs,
  getConversation,
  listConversations,
  streamConversationTurn,
  streamConversationTurnEvents,
  type AcceptedRef,
  type ChatTurn,
  type ComposerRef,
  type ComposerRefKind,
  type ConversationSummary,
  type TurnStreamEvent,
  type StreamTransportState,
} from "@/features/chat-shell/api";
import { listMemberDomains, type MemberDomain } from "@/features/domains/api";
import type { AssistantBlock, ChatMessage, EvidenceRow } from "@/features/chat-shell/types";

const MAX_SELECTED_REFS = 10;

function requestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `turn-${crypto.randomUUID()}`;
  }
  return `turn-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function messageForError(error: unknown): string {
  if (isApiError(error)) return error.message;
  return "Request failed.";
}

function mentionQuery(value: string): string | null {
  const marker = value.lastIndexOf("@");
  if (marker < 0) return null;
  const suffix = value.slice(marker + 1);
  if (suffix.includes("\n")) return null;
  return suffix.split(/\s/)[0] ?? "";
}

function turnToMessages(turn: ChatTurn): ChatMessage[] {
  /* Evidence rows are not timeline blocks; the Evidence Panel renders them. */
  const blocks: AssistantBlock[] = [];
  if (turn.assistantAnswer) {
    blocks.push({ kind: "text", id: `${turn.id}-text`, text: turn.assistantAnswer });
  }
  if (turn.safeError?.message) {
    blocks.push({ kind: "error", id: `${turn.id}-error`, text: turn.safeError.message });
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
  const [composerKind, setComposerKind] = useState<ComposerRefKind>("source");
  const [composerQuery, setComposerQuery] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [discoveredRefs, setDiscoveredRefs] = useState<ComposerRef[]>([]);
  const [selectedRefs, setSelectedRefs] = useState<ComposerRef[]>([]);
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
  const [loading, setLoading] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamTransportState, setStreamTransportState] = useState<StreamTransportState>("connected");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void listConversations()
      .then((rows) => {
        if (!cancelled) setConversations(rows);
      })
      .catch(() => undefined);
    void listMemberDomains()
      .then((rows) => {
        if (!cancelled) setDomains(rows);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const loadConversation = useCallback(async (conversationId: string, options?: { turnId?: string | null }) => {
    setLoading(true);
    setError(null);
    setStreamingTurnId(null);
    setReplayingTurnId(null);
    try {
      const detail = await getConversation(conversationId);
      setConversation(detail.conversation);
      setTurns(detail.turns);
      setSelectedEvidenceId(null);
      const restoreTurnId = options?.turnId?.trim() || null;
      const restoreTurn = restoreTurnId ? detail.turns.find((row) => row.id === restoreTurnId) : null;
      if (restoreTurn) {
        setSelectedTurnId(restoreTurn.id);
        setPanelOpen(restoreTurn.evidence.length > 0);
      } else {
        setSelectedTurnId(null);
        const lastTurn = detail.turns[detail.turns.length - 1];
        setPanelOpen((lastTurn?.evidence.length ?? 0) > 0);
      }
    } catch (err) {
      setError(messageForError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const startConversation = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const created = await createConversation("Chat");
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
      return created.id;
    } catch (err) {
      setError(messageForError(err));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshDiscovery = useCallback(async () => {
    if (!conversation || !pickerOpen) return;
    setDiscovering(true);
    try {
      const refs = await discoverComposerRefs({
        conversationId: conversation.id,
        domainId: domainId.trim() || undefined,
        kinds: [composerKind],
        query: composerQuery || undefined,
        limit: 10,
      });
      setDiscoveredRefs(refs);
    } catch (err) {
      setError(messageForError(err));
      setDiscoveredRefs([]);
    } finally {
      setDiscovering(false);
    }
  }, [composerKind, composerQuery, conversation, domainId, pickerOpen]);

  useEffect(() => {
    void refreshDiscovery();
  }, [refreshDiscovery]);

  const updateInput = useCallback((value: string) => {
    setInput(value);
    const query = mentionQuery(value);
    if (query === null) return;
    setPickerOpen(true);
    setComposerQuery(query);
  }, []);

  const addRef = useCallback((ref: ComposerRef) => {
    setSelectedRefs((current) => {
      if (current.some((item) => item.refToken === ref.refToken)) return current;
      if (current.length >= MAX_SELECTED_REFS) return current;
      return [...current, ref];
    });
    setPickerOpen(false);
  }, []);

  const removeRef = useCallback((refToken: string) => {
    setSelectedRefs((current) => current.filter((ref) => ref.refToken !== refToken));
  }, []);

  const applyTurnStreamEvent = useCallback((event: TurnStreamEvent) => {
    if (event.type === "turn.accepted") {
      setStreamingTurnId(event.turnId);
      setStreamStage("Preparing answer");
    }
    if (event.type === "route.selected") {
      setStreamStage(event.payload.route === "domain_rag" ? "Preparing grounded answer" : "Answering");
    }
    if (event.type === "retrieval.started") setStreamStage("Retrieving evidence");
    if (event.type === "retrieval.completed") {
      setStreamStage(event.payload.result === "evidence_found" ? "Answering from evidence" : "No grounded context");
    }
    if (event.type === "answer.delta") setStreamText((current) => `${current}${event.payload.text}`);
    if (event.type === "evidence.delta") {
      setStreamEvidence((current) => {
        const known = new Set(current.map((item) => item.id));
        return [...current, ...event.payload.items.filter((item) => !known.has(item.id))];
      });
      if (event.payload.items.length > 0) setPanelOpen(true);
    }
    if (event.type === "turn.completed") {
      setPendingRefs(event.payload.acceptedRefs);
      setStreamingTurnId(null);
      setStreamStage(null);
    }
    if (event.type === "turn.failed" || event.type === "turn.cancelled") {
      setError(event.payload.message);
      setStreamingTurnId(null);
      setStreamStage(null);
    }
    if (event.type === "turn.redacted") {
      setStreamText("");
      setStreamEvidence([]);
      setPendingRefs([]);
      setStreamingTurnId(null);
      setPanelOpen(false);
      setSelectedEvidenceId(null);
    }
  }, []);

  const handleLiveStreamEvent = useCallback(
    (event: TurnStreamEvent) => applyTurnStreamEvent(event),
    [applyTurnStreamEvent],
  );

  const submit = useCallback(
    async (messageOverride?: string) => {
      const message = (messageOverride ?? input).trim();
      if (!message || streaming) return;
      let conversationId = conversation?.id ?? null;
      if (!conversationId) conversationId = await startConversation();
      if (!conversationId) return;

      setStreaming(true);
      setStreamTransportState("connected");
      setStreamingTurnId(null);
      setError(null);
      setStreamText("");
      setStreamStage(null);
      setStreamEvidence([]);
      setPendingRefs([]);
      setPendingMessage(message);
      /* New turn: the panel follows the in-flight turn again. */
      setSelectedTurnId(null);
      setSelectedEvidenceId(null);
      const refs = selectedRefs;
      setInput("");
      setSelectedRefs([]);
      setPickerOpen(false);
      try {
        await streamConversationTurn(
          {
            conversationId,
            clientRequestId: requestId(),
            message,
            domainId: domainId.trim() || undefined,
            composerRefTokens: refs.map((ref) => ref.refToken),
            onEvent: handleLiveStreamEvent,
            onTransportState: setStreamTransportState,
          },
        );
        await loadConversation(conversationId);
      } catch (err) {
        setError(messageForError(err));
        setStreamingTurnId(null);
        setInput((current) => current || message);
      } finally {
        setStreaming(false);
        setStreamStage(null);
        setPendingMessage(null);
      }
    },
    [conversation, domainId, handleLiveStreamEvent, input, loadConversation, selectedRefs, startConversation, streaming],
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
      setError(messageForError(err));
    }
  }, [conversation, loadConversation, runningCancellableTurnId]);

  const replayTurn = useCallback(async () => {
    const turnId = selectedReplayableTurnId;
    if (!conversation || !turnId) return;

    setError(null);
    setReplayingTurnId(turnId);
    try {
      await streamConversationTurnEvents({
        conversationId: conversation.id,
        turnId,
        onEvent: applyTurnStreamEvent,
      });
      await loadConversation(conversation.id, { turnId });
    } catch (err) {
      setError(messageForError(err));
    } finally {
      setReplayingTurnId(null);
    }
  }, [applyTurnStreamEvent, conversation, loadConversation, selectedReplayableTurnId]);

  /* Evidence Panel selection: click an assistant message to bind the panel to
     that turn; a turn with evidence opens the panel. */
  const selectTurn = useCallback(
    (turnId: string | null) => {
      setSelectedTurnId(turnId);
      setSelectedEvidenceId(null);
      if (turnId === null) return;
      const turn = turns.find((row) => row.id === turnId);
      if ((turn?.evidence.length ?? 0) > 0) setPanelOpen(true);
    },
    [turns],
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

  /* Timeline projection: persisted turns plus the live streaming turn.
     Evidence is not projected into blocks; the Evidence Panel renders it. */
  const messages = useMemo<ChatMessage[]>(() => {
    const rows = turns.flatMap(turnToMessages);
    if (pendingMessage !== null) {
      rows.push({ id: "pending-user", role: "user", turnId: null, text: pendingMessage, acceptedRefs: pendingRefs });
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

  return {
    conversations,
    conversation,
    domains,
    messages,
    turns,
    input,
    domainId,
    composerKind,
    composerQuery,
    pickerOpen,
    discoveredRefs,
    selectedRefs,
    streaming,
    streamStage,
    streamTransportState,
    loading,
    discovering,
    error,
    lastUserMessage,
    panelOpen,
    panelEvidence,
    selectedTurnId,
    selectedEvidenceId,
    streamingTurnId,
    runningCancellableTurnId,
    selectedReplayableTurnId,
    replayingTurnId,
    setPanelOpen,
    selectTurn,
    selectEvidence,
    setDomainId,
    setComposerKind,
    setComposerQuery,
    setPickerOpen,
    updateInput,
    addRef,
    removeRef,
    refreshDiscovery,
    loadConversation,
    startConversation,
    submit,
    cancelTurn,
    replayTurn,
    clearError,
  };
}
